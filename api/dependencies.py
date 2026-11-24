from functools import lru_cache
from typing import Callable, Dict, Sequence

from fastapi import Depends, Request

from api.auth.session import SessionClaims, SessionError, require_session
from api.config import Settings, get_settings
from api.services.chat import ChatCancellationRegistry, ChatService
from core.llm import create_chat_client
from core.prompter import Prompter
from core.query_plan import QueryPlan
from core.query_validation import PlanValidator
from core.semantic_context import SemanticContextService
from core.translator import Translator
from database.conversations import ConversationRepository
from database.database_connections import (
    DatabaseConfigurationError,
    DatabaseConnectionRepository,
)
from database.postgres import PostgresAdapter
from database.predefined_queries import PredefinedQueryRepository
from database.query_history import QueryHistoryRepository
from database.users import UserRepository


def _api_error(status_code: int, code: str, message: str):
    from api.app import APIError

    return APIError(status_code, code, message)


def get_api_settings(request: Request) -> Settings:
    return request.app.state.settings


@lru_cache(maxsize=1)
def get_db_adapter() -> PostgresAdapter:
    return PostgresAdapter()


@lru_cache(maxsize=1)
def _get_database_connection_repository(
    session_secret: str,
) -> DatabaseConnectionRepository:
    return DatabaseConnectionRepository(get_db_adapter(), session_secret)


def get_database_connection_repository(
    settings: Settings = Depends(get_api_settings),
) -> DatabaseConnectionRepository:
    return _get_database_connection_repository(settings.session_secret)


@lru_cache(maxsize=1)
def _get_target_db_adapter(session_secret: str) -> PostgresAdapter:
    repository = _get_database_connection_repository(session_secret)
    try:
        connection_string = repository.get_connection_string()
    except DatabaseConfigurationError as exc:
        raise _api_error(
            503,
            "database_configuration_invalid",
            "The target database configuration is invalid.",
        ) from exc
    if connection_string is None:
        raise _api_error(
            503,
            "database_not_configured",
            "Configure the target database before using data operations.",
        )
    try:
        normalized = PostgresAdapter.validate_database_url(connection_string)
    except (DatabaseConfigurationError, ValueError) as exc:
        raise _api_error(
            503,
            "database_configuration_invalid",
            "The target database configuration is invalid.",
        ) from exc
    return PostgresAdapter(database_url=normalized)


def get_target_db_adapter(
    settings: Settings = Depends(get_api_settings),
) -> PostgresAdapter:
    return _get_target_db_adapter(settings.session_secret)


def clear_target_database_caches() -> None:
    _get_target_db_adapter.cache_clear()
    _get_semantic_context.cache_clear()
    get_translator.cache_clear()


@lru_cache(maxsize=1)
def get_user_repository() -> UserRepository:
    return UserRepository(get_db_adapter())


@lru_cache(maxsize=1)
def get_conversation_repository() -> ConversationRepository:
    return ConversationRepository(get_db_adapter())


@lru_cache(maxsize=1)
def get_query_history_repository() -> QueryHistoryRepository:
    database = get_db_adapter()
    ConversationRepository(database).initialize()
    repository = QueryHistoryRepository(database)
    repository.initialize()
    return repository


@lru_cache(maxsize=1)
def get_predefined_query_repository() -> PredefinedQueryRepository:
    return PredefinedQueryRepository(get_db_adapter())


@lru_cache(maxsize=1)
def _get_semantic_context(session_secret: str) -> SemanticContextService:
    return SemanticContextService(_get_target_db_adapter(session_secret))


def get_semantic_context(
    settings: Settings = Depends(get_api_settings),
) -> SemanticContextService:
    return _get_semantic_context(settings.session_secret)


@lru_cache(maxsize=1)
def get_chat_cancellation_registry() -> ChatCancellationRegistry:
    return ChatCancellationRegistry()


def validate_translation_plan(plan: QueryPlan) -> None:
    PlanValidator.validate_plan(
        plan,
        get_semantic_context(get_settings()).get_profile(),
    )


@lru_cache(maxsize=1)
def get_translator(
    settings: Settings = Depends(get_api_settings),
) -> Translator:
    database = get_target_db_adapter(settings)
    prompter = Prompter()
    live_schema = database.get_schema_info()
    semantic_context = get_semantic_context(settings)

    def validate_plan(plan: QueryPlan) -> None:
        PlanValidator.validate_plan(plan, semantic_context.get_profile())

    return Translator(
        system_prompt=prompter.build_system_prompt(live_schema=live_schema),
        planner_prompt=prompter.build_planner_prompt(live_schema=live_schema),
        sql_generation_prompt=prompter.build_sql_generation_prompt(
            live_schema=live_schema
        ),
        model_name=settings.llm.model_name,
        plan_validator=validate_plan,
        chat_client=create_chat_client(settings.llm),
    )


def get_chat_service(
    settings: Settings = Depends(get_api_settings),
    conversation_repository: ConversationRepository = Depends(
        get_conversation_repository
    ),
    translator: Translator = Depends(get_translator),
    database: PostgresAdapter = Depends(get_target_db_adapter),
    query_history_repository: QueryHistoryRepository = Depends(
        get_query_history_repository
    ),
    semantic_context: SemanticContextService = Depends(get_semantic_context),
    cancellation_registry: ChatCancellationRegistry = Depends(
        get_chat_cancellation_registry
    ),
) -> ChatService:
    return ChatService(
        conversation_repository,
        translator,
        database,
        query_history_repository=query_history_repository,
        prompt_limit=settings.prompt_limit,
        result_limit=settings.result_limit,
        semantic_context=semantic_context,
        cancellation_registry=cancellation_registry,
    )


def get_current_session(
    request: Request,
    settings: Settings = Depends(get_api_settings),
) -> SessionClaims:
    try:
        return require_session(request, settings)
    except SessionError as exc:
        raise _api_error(exc.status_code, exc.code, exc.message) from exc


def get_current_profile(
    session: SessionClaims = Depends(get_current_session),
    repository: UserRepository = Depends(get_user_repository),
) -> Dict[str, object]:
    profile = repository.get_profile(session.user_id)
    if profile is None:
        raise _api_error(
            403,
            "account_not_approved",
            "No approved profile is available for this account.",
        )
    return profile


_STATUS_MESSAGES = {
    "pending": "Sua conta aguarda aprovação.",
    "rejected": "Sua solicitação de acesso foi rejeitada.",
    "disabled": "Sua conta está desativada.",
}


def require_approved_user(
    profile: Dict[str, object] = Depends(get_current_profile),
) -> Dict[str, object]:
    status = profile.get("status")
    if status != "approved":
        message = _STATUS_MESSAGES.get(
            str(status),
            "Sua conta não está aprovada.",
        )
        raise _api_error(403, "account_not_approved", message)
    return profile


def require_roles(
    *allowed_roles: str,
) -> Callable:
    allowed = frozenset(allowed_roles)

    def role_dependency(
        profile: Dict[str, object] = Depends(require_approved_user),
    ) -> Dict[str, object]:
        if profile.get("role") not in allowed:
            raise _api_error(
                403,
                "forbidden",
                "You do not have permission for this action.",
            )
        return profile

    return role_dependency
