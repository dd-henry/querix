import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query
from pydantic import ValidationError

from api.app import APIError
from api.config import Settings
from api.dependencies import (
    get_api_settings,
    get_db_adapter,
    get_predefined_query_repository,
    require_approved_user,
    require_roles,
)
from api.schemas.predefined import (
    PredefinedFavoriteRequest,
    PredefinedFavoriteResponse,
    PredefinedQueryExecutionResponse,
    PredefinedQueryListResponse,
    PredefinedQueryMutationResponse,
    PredefinedQuerySchema,
    PredefinedQueryExecuteRequest,
    PredefinedQueryWriteRequest,
)
from api.serializers.results import serialize_dataframe
from database.postgres import PostgresAdapter
from database.predefined_queries import PredefinedQueryRepository

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/predefined-queries",
    tags=["predefined-queries"],
)


def _owner_id(profile: Dict[str, object]) -> str:
    user_id = profile.get("id")
    if not isinstance(user_id, str) or not user_id:
        raise APIError(
            500,
            "invalid_profile",
            "The authenticated profile is incomplete.",
        )
    return user_id


def _profile_email(profile: Dict[str, object]) -> str:
    email = profile.get("email")
    if not isinstance(email, str) or not email.strip():
        raise APIError(
            500,
            "invalid_profile",
            "The authenticated profile is incomplete.",
        )
    return email.strip()


def _query_record(record: Dict[str, object]) -> PredefinedQuerySchema:
    try:
        return PredefinedQuerySchema.model_validate(record)
    except ValidationError as exc:
        raise APIError(
            500,
            "invalid_predefined_query",
            "The shared query record is incomplete.",
        ) from exc


def _owned_query(
    repository: PredefinedQueryRepository,
    user_id: str,
    query_id: int,
) -> PredefinedQuerySchema:
    record = repository.get(user_id, query_id)
    if record is None:
        raise APIError(404, "not_found", "Shared query not found.")
    return _query_record(record)


def _validated_definition(
    payload: PredefinedQueryWriteRequest,
) -> str:
    if not payload.name.strip():
        raise APIError(
            422,
            "validation_error",
            "Shared query name cannot be empty.",
        )
    try:
        return PredefinedQueryRepository.validate_query(
            payload.sql,
            payload.parameters,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise APIError(
            422,
            "sql_not_read_only",
            "Shared query SQL must be a single read-only SELECT or WITH statement.",
        ) from exc


def _validated_parameters(
    definition: List[Dict[str, Any]],
    values: Dict[str, Any],
) -> Dict[str, Any]:
    for parameter in definition:
        name = parameter.get("name")
        required = parameter.get("required", True)
        if (
            required
            and isinstance(name, str)
            and (
                name not in values
                or values[name] is None
                or (
                    isinstance(values[name], str)
                    and not values[name].strip()
                )
            )
        ):
            raise APIError(
                422,
                "missing_parameter",
                f"Missing required parameter: {name}.",
            )
    return values


@router.get("", response_model=PredefinedQueryListResponse)
def list_predefined_queries(
    search: str = Query("", max_length=200),
    profile: Dict[str, object] = Depends(require_approved_user),
    repository: PredefinedQueryRepository = Depends(
        get_predefined_query_repository
    ),
) -> PredefinedQueryListResponse:
    records = repository.list(_owner_id(profile), search=search.strip())
    return PredefinedQueryListResponse(
        queries=[_query_record(record) for record in records]
    )


@router.patch(
    "/{query_id}/favorite",
    response_model=PredefinedFavoriteResponse,
)
def update_predefined_favorite(
    query_id: int,
    payload: PredefinedFavoriteRequest,
    profile: Dict[str, object] = Depends(require_approved_user),
    repository: PredefinedQueryRepository = Depends(
        get_predefined_query_repository
    ),
) -> PredefinedFavoriteResponse:
    user_id = _owner_id(profile)
    _owned_query(repository, user_id, query_id)
    repository.toggle_favorite(user_id, query_id, payload.is_favorite)
    return PredefinedFavoriteResponse(
        id=query_id,
        is_favorite=payload.is_favorite,
    )


@router.post(
    "",
    response_model=PredefinedQueryMutationResponse,
    status_code=201,
)
def create_predefined_query(
    payload: PredefinedQueryWriteRequest,
    profile: Dict[str, object] = Depends(
        require_roles("dev", "dba", "admin")
    ),
    repository: PredefinedQueryRepository = Depends(
        get_predefined_query_repository
    ),
) -> PredefinedQueryMutationResponse:
    sql = _validated_definition(payload)
    repository.create(
        payload.name,
        payload.description,
        sql,
        [tag.strip() for tag in payload.tags if tag.strip()],
        _profile_email(profile),
        payload.parameters,
    )
    return PredefinedQueryMutationResponse(status="created")


@router.patch(
    "/{query_id}",
    response_model=PredefinedQueryMutationResponse,
)
def update_predefined_query(
    query_id: int,
    payload: PredefinedQueryWriteRequest,
    profile: Dict[str, object] = Depends(
        require_roles("dev", "dba", "admin")
    ),
    repository: PredefinedQueryRepository = Depends(
        get_predefined_query_repository
    ),
) -> PredefinedQueryMutationResponse:
    sql = _validated_definition(payload)
    repository.update(
        query_id,
        payload.name,
        payload.description,
        sql,
        [tag.strip() for tag in payload.tags if tag.strip()],
        payload.parameters,
    )
    return PredefinedQueryMutationResponse(status="updated")


@router.delete(
    "/{query_id}",
    response_model=PredefinedQueryMutationResponse,
)
def delete_predefined_query(
    query_id: int,
    profile: Dict[str, object] = Depends(
        require_roles("dev", "dba", "admin")
    ),
    repository: PredefinedQueryRepository = Depends(
        get_predefined_query_repository
    ),
) -> PredefinedQueryMutationResponse:
    repository.delete(query_id)
    return PredefinedQueryMutationResponse(status="deleted")


@router.post(
    "/{query_id}/execute",
    response_model=PredefinedQueryExecutionResponse,
)
def execute_predefined_query(
    query_id: int,
    payload: PredefinedQueryExecuteRequest,
    profile: Dict[str, object] = Depends(require_approved_user),
    repository: PredefinedQueryRepository = Depends(
        get_predefined_query_repository
    ),
    database: PostgresAdapter = Depends(get_db_adapter),
    settings: Settings = Depends(get_api_settings),
) -> PredefinedQueryExecutionResponse:
    user_id = _owner_id(profile)
    query = _owned_query(repository, user_id, query_id)
    definition = [parameter.model_dump() for parameter in query.parameters]
    parameters = _validated_parameters(definition, payload.parameters)
    try:
        sql = PredefinedQueryRepository.validate_query(
            query.sql,
            definition,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise APIError(
            422,
            "sql_not_read_only",
            "Shared query SQL must be a single read-only SELECT or WITH statement.",
        ) from exc
    try:
        dataframe = database.execute_read_only_query(
            sql,
            parameters,
        )
        result = serialize_dataframe(
            dataframe,
            max_rows=settings.result_limit,
        )
    except Exception as exc:
        logger.exception("Shared query execution failed.")
        raise APIError(
            503,
            "database_unavailable",
            "The database is unavailable.",
        ) from exc
    return PredefinedQueryExecutionResponse(
        query_id=query.id,
        result=result,
    )
