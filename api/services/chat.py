import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, NoReturn, Optional
from uuid import UUID

from api.serializers.results import (
    ResultPayload,
    serialize_dataframe,
    summarize_result,
)
from core.query_plan import QueryPlan, QueryPlanError
from core.query_validation import PlanValidator, QueryValidationError
from core.result_quality import build_interpretation, critique_result
from core.semantic_context import SemanticContextService
from database.conversations import ConversationRepository
from database.postgres import PostgresAdapter
from database.predefined_queries import PredefinedQueryRepository
from database.query_history import QueryHistoryRepository

logger = logging.getLogger(__name__)


class ChatServiceError(RuntimeError):
    """An expected chat operation failure exposed by the API layer."""

    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass
class ChatInsight:
    key: str
    title: str
    summary: Optional[str] = None
    sql: Optional[str] = None
    result: Optional[ResultPayload] = None
    warning: Optional[str] = None


@dataclass
class ChatResult:
    conversation_id: UUID
    request_id: UUID
    status: str
    content: str
    sql: Optional[str] = None
    chart: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    result: Optional[ResultPayload] = None
    insights: List[ChatInsight] = field(default_factory=list)
    retryable: bool = False
    retry_kind: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    interpretation: Optional[Dict[str, Any]] = None
    diagnostics: Optional[Dict[str, Any]] = None


class ChatService:
    """Orchestrate chat persistence, translation, validation, and execution."""

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        translator: Any,
        database: PostgresAdapter,
        query_history_repository: Optional[QueryHistoryRepository] = None,
        prompt_limit: int = 2_000,
        result_limit: int = 5_000,
        semantic_context: Optional[SemanticContextService] = None,
    ):
        self.conversation_repository = conversation_repository
        self.translator = translator
        self.database = database
        self.query_history_repository = query_history_repository
        self.prompt_limit = prompt_limit
        self.result_limit = result_limit
        self.semantic_context = semantic_context

    def translate_prompt(
        self,
        user_id: str,
        conversation_id: UUID,
        request_id: UUID,
        prompt: str,
        review_mode: bool = True,
        retry: bool = False,
    ) -> ChatResult:
        normalized_prompt = self._validate_prompt(prompt)
        messages = self.conversation_repository.get_messages(
            user_id,
            conversation_id,
        )
        if not retry:
            existing = self._existing_result(
                messages,
                conversation_id,
                request_id,
            )
            if existing is not None:
                return existing

        if not retry:
            self._persist_user_turn(
                user_id,
                conversation_id,
                request_id,
                normalized_prompt,
                messages,
            )

        context = self.conversation_repository.get_context(
            user_id,
            conversation_id,
            limit=6,
            exclude_request_id=request_id if retry else None,
        )
        try:
            translated = self.translator.translate_to_sql(
                normalized_prompt,
                conversation_context=context,
            )
        except QueryValidationError as exc:
            logger.warning("Generated query plan failed validation: %s", exc)
            self._persist_assistant_turn(
                user_id,
                conversation_id,
                request_id,
                "O plano analítico gerado não corresponde ao esquema atual.",
                error="query_plan_invalid",
                metadata={"validation_code": getattr(exc, "code", "invalid_plan")},
            )
            raise ChatServiceError(
                422,
                "query_plan_invalid",
                str(exc),
            ) from exc
        except Exception as exc:
            logger.exception("Chat translation failed.")
            self._persist_assistant_turn(
                user_id,
                conversation_id,
                request_id,
                "Não foi possível traduzir a pergunta.",
                error="translator_unavailable",
                metadata={
                    "retryable": True,
                    "retry_kind": "translate",
                },
            )
            raise ChatServiceError(
                502,
                "translator_unavailable",
                "The translator service is unavailable.",
            ) from exc

        if not isinstance(translated, Mapping):
            return self._handle_translation_failure(
                user_id,
                conversation_id,
                request_id,
                ValueError("The translator returned an invalid response."),
            )

        raw_sql = translated.get("sql")
        sql = raw_sql.strip() if isinstance(raw_sql, str) else ""
        chart = translated.get("grafico")
        parameters = translated.get("parameters")
        if not isinstance(parameters, Mapping):
            parameters = {}
        parameters = {str(key): value for key, value in parameters.items()}
        intent = translated.get("intent")
        supporting_queries = self._prepare_supporting_queries(
            translated.get("supporting_queries")
        )
        temporal = translated.get("temporal")
        plan = self._validate_plan(
            translated.get("plan"),
            user_id,
            conversation_id,
            request_id,
        )
        if sql.startswith("AVISO:"):
            self._persist_assistant_turn(
                user_id,
                conversation_id,
                request_id,
                sql,
                metadata={"grafico": chart},
            )
            return ChatResult(
                conversation_id=conversation_id,
                request_id=request_id,
                status="warning",
                content=sql,
                chart=chart,
                interpretation=build_interpretation(plan, temporal),
            )
        if not sql:
            return self._handle_translation_failure(
                user_id,
                conversation_id,
                request_id,
                ValueError("The translator returned no SQL."),
            )

        try:
            normalized_sql = PlanValidator.validate_sql(sql)
        except QueryValidationError as exc:
            self._persist_assistant_turn(
                user_id,
                conversation_id,
                request_id,
                "A consulta gerada não é somente leitura.",
                sql=sql,
                error="sql_not_read_only",
                metadata={"grafico": chart},
            )
            raise ChatServiceError(
                422,
                "sql_not_read_only",
                "Generated SQL must be a single read-only SELECT or WITH statement.",
            ) from exc

        content = (
            "SQL gerado para revisão."
            if review_mode
            else "SQL gerado; consulta em execução."
        )
        self._persist_assistant_turn(
            user_id,
            conversation_id,
            request_id,
            content,
            sql=normalized_sql,
            metadata={
                "grafico": chart,
                "parameters": parameters,
                "intent": intent,
                "supporting_queries": supporting_queries,
                "plan": plan.to_dict() if plan is not None else None,
                "temporal": temporal,
                "interpretation": build_interpretation(plan, temporal),
            },
        )
        return ChatResult(
            conversation_id=conversation_id,
            request_id=request_id,
            status="review" if review_mode else "translated",
            content=content,
            sql=normalized_sql,
            chart=chart,
            interpretation=build_interpretation(plan, temporal),
        )

    def _validate_plan(
        self,
        value: object,
        user_id: str,
        conversation_id: UUID,
        request_id: UUID,
    ) -> Optional[QueryPlan]:
        if value is None:
            return None
        try:
            plan = value if isinstance(value, QueryPlan) else QueryPlan.from_payload(value)
            if self.semantic_context is not None:
                PlanValidator.validate_plan(
                    plan,
                    self.semantic_context.get_profile(),
                )
            return plan
        except (QueryPlanError, QueryValidationError) as exc:
            self._persist_assistant_turn(
                user_id,
                conversation_id,
                request_id,
                "O plano analítico gerado não corresponde ao esquema atual.",
                error="query_plan_invalid",
                metadata={"validation_code": getattr(exc, "code", "invalid_plan")},
            )
            raise ChatServiceError(
                422,
                "query_plan_invalid",
                str(exc),
            ) from exc

    def execute_stored_query(
        self,
        user_id: str,
        conversation_id: UUID,
        request_id: UUID,
    ) -> ChatResult:
        messages = self.conversation_repository.get_messages(
            user_id,
            conversation_id,
        )
        assistant = self._find_message(messages, request_id, "assistant")
        if assistant is None or not assistant.get("sql"):
            raise ChatServiceError(
                404,
                "stored_query_not_found",
                "No stored query is available for this request.",
            )

        raw_sql = str(assistant["sql"]).strip()
        try:
            sql = PredefinedQueryRepository.validate_query(raw_sql, [])
        except (AttributeError, TypeError, ValueError) as exc:
            self._persist_assistant_turn(
                user_id,
                conversation_id,
                request_id,
                "A consulta armazenada não é somente leitura.",
                sql=raw_sql,
                error="sql_not_read_only",
                metadata=self._metadata(assistant),
            )
            raise ChatServiceError(
                422,
                "sql_not_read_only",
                "Stored SQL must be a single read-only SELECT or WITH statement.",
            ) from exc

        metadata = self._metadata(assistant)
        parameters = metadata.get("parameters") or {}
        if not isinstance(parameters, dict):
            parameters = {}
        try:
            dataframe = self.database.execute_read_only_query(sql, parameters)
            result = serialize_dataframe(dataframe, max_rows=self.result_limit)
            summary = summarize_result(result)
        except Exception as exc:
            logger.exception("Stored query execution failed.")
            repaired = self._attempt_query_repair(
                sql,
                exc,
                metadata,
                messages,
                request_id,
            )
            if repaired is None:
                self._raise_database_failure(
                    user_id,
                    conversation_id,
                    request_id,
                    sql,
                    metadata,
                    exc,
                )
            sql, parameters, metadata = repaired
            try:
                dataframe = self.database.execute_read_only_query(
                    sql,
                    parameters,
                )
                result = serialize_dataframe(
                    dataframe,
                    max_rows=self.result_limit,
                )
                summary = summarize_result(result)
            except Exception as repair_error:
                logger.exception("Repaired query execution failed.")
                self._raise_database_failure(
                    user_id,
                    conversation_id,
                    request_id,
                    sql,
                    metadata,
                    repair_error,
                )

        insights = self._execute_supporting_queries(
            metadata.get("supporting_queries"),
        )
        interpretation = metadata.get("interpretation")
        if not isinstance(interpretation, dict):
            interpretation = build_interpretation(
                metadata.get("plan"),
                metadata.get("temporal"),
            )
        diagnostics = critique_result(result, metadata.get("plan"))

        warnings = self._record_history(
            user_id,
            conversation_id,
            str(
                (
                    self._find_message(messages, request_id, "user")
                    or {}
                ).get("content") or ""
            ),
            sql,
            parameters,
            metadata,
        )
        self._persist_assistant_turn(
            user_id,
            conversation_id,
            request_id,
            "Aqui estão os resultados da consulta:",
            sql=sql,
            metadata={
                **metadata,
                "grafico": metadata.get("grafico"),
                "source": metadata.get("source", "chat"),
                "parameters": parameters,
                "interpretation": interpretation,
                "diagnostics": (
                    diagnostics.to_dict() if diagnostics is not None else None
                ),
            },
        )
        return ChatResult(
            conversation_id=conversation_id,
            request_id=request_id,
            status="executed",
            content="Aqui estão os resultados da consulta:",
            sql=sql,
            chart=metadata.get("grafico"),
            result=result,
            summary=summary,
            insights=insights,
            warnings=warnings,
            interpretation=interpretation,
            diagnostics=(
                diagnostics.to_dict() if diagnostics is not None else None
            ),
        )

    def _attempt_query_repair(
        self,
        sql: str,
        database_error: Exception,
        metadata: Mapping[str, object],
        messages: List[Dict[str, object]],
        request_id: UUID,
    ) -> Optional[tuple[str, Dict[str, object], Dict[str, object]]]:
        if metadata.get("repair_attempted"):
            return None
        repair_query = getattr(self.translator, "repair_query", None)
        if not callable(repair_query):
            return None

        user_message = self._find_message(
            messages,
            request_id,
            "user",
        )
        user_question = str((user_message or {}).get("content") or "")
        try:
            repaired = repair_query(
                sql=sql,
                database_error=str(database_error),
                plan=metadata.get("plan"),
                user_question=user_question,
                conversation_context=[],
            )
            if not isinstance(repaired, Mapping):
                raise ValueError("The repair response must be an object.")
            repaired_sql = repaired.get("sql")
            if not isinstance(repaired_sql, str) or not repaired_sql.strip():
                raise ValueError("The repair response did not contain SQL.")
            normalized_sql = PlanValidator.validate_sql(repaired_sql)
            raw_parameters = repaired.get("parameters", metadata.get("parameters", {}))
            parameters = (
                dict(raw_parameters)
                if isinstance(raw_parameters, Mapping)
                else {}
            )
            return (
                normalized_sql,
                parameters,
                {
                    **dict(metadata),
                    "parameters": parameters,
                    "repair_attempted": True,
                    "repaired_from": sql,
                },
            )
        except Exception as exc:
            logger.warning("Stored query repair was not accepted: %s", exc)
            return None

    def _raise_database_failure(
        self,
        user_id: str,
        conversation_id: UUID,
        request_id: UUID,
        sql: str,
        metadata: Mapping[str, object],
        error: Exception,
    ) -> NoReturn:
        self._persist_assistant_turn(
            user_id,
            conversation_id,
            request_id,
            "Houve um problema ao executar a consulta.",
            sql=sql,
            error="database_unavailable",
            metadata={
                **dict(metadata),
                "repair_attempted": True,
                "retryable": True,
                "retry_kind": "execute",
            },
        )
        raise ChatServiceError(
            503,
            "database_unavailable",
            "The database is unavailable.",
        ) from error

    def execute_history_query(
        self,
        user_id: str,
        history_id: int,
        conversation_id: UUID,
        request_id: UUID,
    ) -> ChatResult:
        if self.query_history_repository is None:
            raise ChatServiceError(
                503,
                "storage_unavailable",
                "Query history is unavailable.",
            )
        history = self.query_history_repository.get(user_id, history_id)
        if history is None:
            raise ChatServiceError(
                404,
                "history_not_found",
                "History record not found.",
            )

        raw_sql = str(history.get("sql") or "").strip()
        try:
            sql = PredefinedQueryRepository.validate_query(raw_sql, [])
        except (AttributeError, TypeError, ValueError) as exc:
            raise ChatServiceError(
                422,
                "sql_not_read_only",
                "Stored SQL must be a single read-only SELECT or WITH statement.",
            ) from exc

        parameters = history.get("parameters") or {}
        if not isinstance(parameters, dict):
            parameters = {}
        prompt = str(history.get("prompt") or "Consulta do histórico")
        messages = self.conversation_repository.get_messages(
            user_id,
            conversation_id,
        )
        self._persist_user_turn(
            user_id,
            conversation_id,
            request_id,
            prompt,
            messages,
        )
        self._persist_assistant_turn(
            user_id,
            conversation_id,
            request_id,
            "SQL do histórico pronto para execução.",
            sql=sql,
            metadata={
                "source": "chat",
                "parameters": parameters,
            },
        )
        return self.execute_stored_query(
            user_id,
            conversation_id,
            request_id,
        )

    def retry_request(
        self,
        user_id: str,
        conversation_id: UUID,
        request_id: UUID,
    ) -> ChatResult:
        messages = self.conversation_repository.get_messages(
            user_id,
            conversation_id,
        )
        user_message = self._find_message(messages, request_id, "user")
        assistant = self._find_message(messages, request_id, "assistant")
        if user_message is None or assistant is None:
            raise ChatServiceError(
                404,
                "request_not_found",
                "No retryable request is available.",
            )

        retry_kind = self._metadata(assistant).get("retry_kind")
        if retry_kind == "translate":
            return self.translate_prompt(
                user_id,
                conversation_id,
                request_id,
                str(user_message.get("content") or ""),
                review_mode=True,
                retry=True,
            )
        if retry_kind == "execute":
            return self.execute_stored_query(
                user_id,
                conversation_id,
                request_id,
            )
        raise ChatServiceError(
            422,
            "request_not_retryable",
            "This request cannot be retried.",
        )

    def _validate_prompt(self, prompt: str) -> str:
        normalized = (prompt or "").strip()
        if not normalized or len(normalized) > self.prompt_limit:
            raise ChatServiceError(
                422,
                "validation_error",
                f"Prompt must contain between 1 and {self.prompt_limit} characters.",
            )
        return normalized

    def _persist_user_turn(
        self,
        user_id: str,
        conversation_id: UUID,
        request_id: UUID,
        prompt: str,
        messages: List[Dict[str, object]],
    ) -> None:
        if self._find_message(messages, request_id, "user") is not None:
            return
        if messages:
            self.conversation_repository.append_message(
                user_id,
                conversation_id,
                request_id,
                "user",
                prompt,
            )
        else:
            self.conversation_repository.create_with_user_message(
                user_id,
                conversation_id,
                request_id,
                prompt,
            )

    def _persist_assistant_turn(
        self,
        user_id: str,
        conversation_id: UUID,
        request_id: UUID,
        content: str,
        sql: Optional[str] = None,
        error: Optional[str] = None,
        metadata: Optional[Mapping[str, object]] = None,
    ) -> None:
        existing = self.conversation_repository.get_messages(
            user_id,
            conversation_id,
        )
        values = dict(metadata or {})
        if self._find_message(existing, request_id, "assistant") is not None:
            self.conversation_repository.update_assistant_message(
                user_id,
                conversation_id,
                request_id,
                content,
                sql=sql,
                error=error,
                metadata=values,
            )
        else:
            self.conversation_repository.append_message(
                user_id,
                conversation_id,
                request_id,
                "assistant",
                content,
                sql=sql,
                error=error,
                metadata=values,
            )

    def _handle_translation_failure(
        self,
        user_id: str,
        conversation_id: UUID,
        request_id: UUID,
        error: Exception,
    ) -> NoReturn:
        logger.error("Translator returned an invalid response: %s", error)
        self._persist_assistant_turn(
            user_id,
            conversation_id,
            request_id,
            "Não foi possível traduzir a pergunta.",
            error="translator_unavailable",
            metadata={
                "retryable": True,
                "retry_kind": "translate",
            },
        )
        raise ChatServiceError(
            502,
            "translator_unavailable",
            "The translator service is unavailable.",
        ) from error

    def _record_history(
        self,
        user_id: str,
        conversation_id: UUID,
        prompt: str,
        sql: str,
        parameters: Dict[str, object],
        metadata: Mapping[str, object],
    ) -> List[str]:
        if self.query_history_repository is None:
            return []

        try:
            self.query_history_repository.record(
                user_id,
                prompt,
                sql,
                metadata.get("source", "chat"),
                parameters,
                session_id=conversation_id,
            )
        except Exception as exc:
            logger.exception("Could not save query history.")
            return [
                f"A consulta foi executada, mas não foi salva no histórico. ({exc})"
            ]
        return []

    @staticmethod
    def _prepare_supporting_queries(value: object) -> List[Dict[str, object]]:
        if not isinstance(value, list):
            return []

        prepared: List[Dict[str, object]] = []
        for index, item in enumerate(value[:3]):
            if not isinstance(item, Mapping):
                continue
            key = item.get("key")
            title = item.get("title")
            raw_sql = item.get("sql")
            parameters = item.get("parameters") or {}
            if (
                not isinstance(key, str)
                or not key.strip()
                or not isinstance(title, str)
                or not title.strip()
                or not isinstance(raw_sql, str)
                or not raw_sql.strip()
                or not isinstance(parameters, Mapping)
            ):
                continue

            support: Dict[str, object] = {
                "key": key.strip(),
                "title": title.strip(),
                "sql": raw_sql.strip(),
                "parameters": dict(parameters),
            }
            try:
                support["sql"] = PredefinedQueryRepository.validate_query(
                    raw_sql,
                    [],
                )
            except (AttributeError, TypeError, ValueError) as exc:
                support["validation_error"] = (
                    "A consulta complementar não é somente leitura."
                )
                logger.warning(
                    "Supporting query %s was rejected before execution: %s",
                    index,
                    exc,
                )
            prepared.append(support)
        return prepared

    def _execute_supporting_queries(
        self,
        value: object,
    ) -> List[ChatInsight]:
        if not isinstance(value, list):
            return []

        insights: List[ChatInsight] = []
        for item in value[:3]:
            if not isinstance(item, Mapping):
                continue
            key = str(item.get("key") or "supporting_query")
            title = str(item.get("title") or "Análise complementar")
            validation_error = item.get("validation_error")
            if validation_error:
                insights.append(
                    ChatInsight(
                        key=key,
                        title=title,
                        warning=str(validation_error),
                    )
                )
                continue

            raw_sql = item.get("sql")
            if not isinstance(raw_sql, str) or not raw_sql.strip():
                insights.append(
                    ChatInsight(
                        key=key,
                        title=title,
                        warning="A consulta complementar está vazia.",
                    )
                )
                continue
            try:
                sql = PredefinedQueryRepository.validate_query(raw_sql, [])
            except (AttributeError, TypeError, ValueError) as exc:
                logger.warning(
                    "Stored supporting query %s failed validation: %s",
                    key,
                    exc,
                )
                insights.append(
                    ChatInsight(
                        key=key,
                        title=title,
                        warning=(
                            "A consulta complementar foi rejeitada por "
                            "não ser somente leitura."
                        ),
                    )
                )
                continue

            parameters = item.get("parameters") or {}
            if not isinstance(parameters, dict):
                parameters = {}
            try:
                dataframe = self.database.execute_read_only_query(
                    sql,
                    parameters,
                )
                result = serialize_dataframe(
                    dataframe,
                    max_rows=self.result_limit,
                )
            except Exception:
                logger.exception(
                    "Supporting query %s execution failed.",
                    key,
                )
                insights.append(
                    ChatInsight(
                        key=key,
                        title=title,
                        sql=sql,
                        warning=(
                            "Não foi possível calcular esta análise "
                            "complementar."
                        ),
                    )
                )
                continue

            insights.append(
                ChatInsight(
                    key=key,
                    title=title,
                    summary=summarize_result(result),
                    sql=sql,
                    result=result,
                )
            )
        return insights

    @staticmethod
    def _find_message(
        messages: List[Dict[str, object]],
        request_id: UUID,
        role: str,
    ) -> Optional[Dict[str, object]]:
        request_value = str(request_id)
        for message in messages:
            if (
                message.get("role") == role
                and str(message.get("request_id")) == request_value
            ):
                return message
        return None

    @staticmethod
    def _metadata(message: Mapping[str, object]) -> Dict[str, object]:
        metadata = message.get("metadata")
        return dict(metadata) if isinstance(metadata, Mapping) else {}

    def _existing_result(
        self,
        messages: List[Dict[str, object]],
        conversation_id: UUID,
        request_id: UUID,
    ) -> Optional[ChatResult]:
        assistant = self._find_message(messages, request_id, "assistant")
        if assistant is None:
            return None
        metadata = self._metadata(assistant)
        error = assistant.get("error")
        if error:
            raise ChatServiceError(
                {
                    "translator_unavailable": 502,
                    "database_unavailable": 503,
                    "sql_not_read_only": 422,
                }.get(str(error), 500),
                str(error),
                str(assistant.get("content") or "The request failed."),
            )
        sql = assistant.get("sql")
        content = str(assistant.get("content") or "")
        status = "warning" if content.startswith("AVISO:") else "review"
        return ChatResult(
            conversation_id=conversation_id,
            request_id=request_id,
            status=status,
            content=content,
            sql=str(sql) if sql else None,
            chart=metadata.get("grafico"),
            retryable=bool(metadata.get("retryable")),
            retry_kind=metadata.get("retry_kind"),
            interpretation=(
                metadata.get("interpretation")
                if isinstance(metadata.get("interpretation"), dict)
                else None
            ),
            diagnostics=(
                metadata.get("diagnostics")
                if isinstance(metadata.get("diagnostics"), dict)
                else None
            ),
        )
