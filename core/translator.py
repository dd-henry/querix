import re
import json
from collections.abc import Mapping
from datetime import date
from typing import Any, Callable, Dict, List, Optional, Sequence

import ollama

from core.query_plan import QueryPlan, QueryPlanError
from core.query_validation import QueryValidationError
from core.temporal import TemporalInterpretation, TemporalInterpreter


class Translator:
    """
    Motor de tradução que usa um cliente LLM configurável para converter
    linguagem natural em consultas SQL.
    """

    def __init__(
        self,
        system_prompt: str,
        model_name: str = "qwen2.5-coder:7b",
        planner_prompt: Optional[str] = None,
        sql_generation_prompt: Optional[str] = None,
        plan_validator: Optional[Callable[[QueryPlan], None]] = None,
        chat_client: Optional[Callable[..., Mapping[str, Any]]] = None,
    ):
        """
        Inicializa o tradutor com o prompt de sistema configurado e o modelo desejado.
        
        Args:
            system_prompt (str): O contexto consolidado de banco de dados e regras de negócio.
            model_name (str): O nome do modelo configurado no provedor selecionado.
        """
        self.system_prompt = system_prompt
        self.model_name = model_name
        self.planner_prompt = planner_prompt
        self.sql_generation_prompt = sql_generation_prompt
        self.plan_validator = plan_validator
        self.chat_client = chat_client
        self._planner_max_attempts = 2

    def _clean_sql_response(self, text: str) -> dict:
        """
        Extrai e formata o JSON retornado pelo modelo, garantindo que contenha 
        a query SQL e a configuração do gráfico (quando aplicável).
        """
        if text.strip().startswith("AVISO:"):
            return {"sql": text.strip(), "grafico": None}
            
        # Busca pelo primeiro '{' e o último '}' para isolar o JSON puramente
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            json_str = text[start_idx:end_idx+1]
            try:
                payload = json.loads(json_str)
                if not isinstance(payload, dict):
                    raise ValueError("The model response must be a JSON object.")
                payload["supporting_queries"] = (
                    self._normalize_supporting_queries(
                        payload.get("supporting_queries")
                    )
                )
                return payload
            except json.JSONDecodeError:
                raise ValueError(f"O modelo não retornou um JSON válido. Retorno isolado: {json_str}")
        else:
            raise ValueError("Não foi possível encontrar um objeto JSON válido na resposta do modelo.")

    @staticmethod
    def _normalize_supporting_queries(value: object) -> List[dict]:
        if value is None:
            return []
        if not isinstance(value, list) or len(value) > 3:
            return []

        normalized: List[dict] = []
        keys = set()
        for item in value:
            if not isinstance(item, Mapping):
                return []
            key = item.get("key")
            title = item.get("title")
            sql = item.get("sql")
            parameters = item.get("parameters", {})
            if (
                not isinstance(key, str)
                or not key.strip()
                or not isinstance(title, str)
                or not title.strip()
                or not isinstance(sql, str)
                or not sql.strip()
                or not isinstance(parameters, Mapping)
                or key in keys
            ):
                return []
            keys.add(key)
            normalized.append(
                {
                    "key": key.strip(),
                    "title": title.strip(),
                    "sql": sql.strip(),
                    "parameters": dict(parameters),
                }
            )
        return normalized

    def _clean_plan_response(self, text: str) -> QueryPlan:
        try:
            payload = self._extract_json_payload(text)
            return QueryPlan.from_payload(payload)
        except (QueryPlanError, ValueError) as exc:
            raise TranslationStageError("planning", str(exc)) from exc

    @staticmethod
    def _extract_json_payload(text: str) -> dict:
        start_idx = text.find("{")
        end_idx = text.rfind("}")
        if start_idx == -1 or end_idx == -1:
            raise ValueError(
                "The model did not return a JSON object for this translation stage."
            )
        try:
            payload = json.loads(text[start_idx : end_idx + 1])
        except json.JSONDecodeError as exc:
            raise ValueError("The model returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise ValueError("The model response must be a JSON object.")
        return payload

    def plan_question(
        self,
        user_question: str,
        conversation_context: Optional[Sequence[Dict[str, str]]] = None,
        temporal_interpretation: Optional[TemporalInterpretation] = None,
        planner_feedback: Optional[str] = None,
    ) -> QueryPlan:
        if not self.planner_prompt:
            raise TranslationStageError(
                "planning",
                "A planner prompt is not configured for this translator.",
            )

        temporal = temporal_interpretation or TemporalInterpreter().interpret(
            user_question,
            date.today(),
        )
        prompt = self._append_temporal_hint(self.planner_prompt, temporal)
        for attempt in range(self._planner_max_attempts):
            attempt_prompt = self._append_planner_feedback(
                prompt,
                planner_feedback,
            )
            messages = self._stage_messages(
                attempt_prompt,
                user_question,
                conversation_context,
            )
            try:
                response = self._chat(messages)
            except Exception as exc:
                raise TranslationStageError("planning", str(exc)) from exc

            raw_content = response.get("message", {}).get("content", "")
            try:
                return self._clean_plan_response(raw_content)
            except TranslationStageError as exc:
                if attempt + 1 >= self._planner_max_attempts:
                    raise
                planner_feedback = str(exc)

        raise TranslationStageError(
            "planning",
            "The planner did not return a valid query plan.",
        )

    def translate_plan_to_sql(
        self,
        plan: QueryPlan,
        user_question: str,
        conversation_context: Optional[Sequence[Dict[str, str]]] = None,
        temporal_interpretation: Optional[TemporalInterpretation] = None,
    ) -> dict:
        if not isinstance(plan, QueryPlan):
            raise TranslationStageError(
                "sql_generation",
                "SQL generation requires a normalized query plan.",
            )
        if self.plan_validator is not None:
            self.plan_validator(plan)
        if not self.sql_generation_prompt:
            raise TranslationStageError(
                "sql_generation",
                "An SQL generation prompt is not configured for this translator.",
            )

        temporal = temporal_interpretation or TemporalInterpreter().interpret(
            user_question,
            date.today(),
        )
        plan_context = json.dumps(
            plan.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
        )
        prompt = (
            f"{self.sql_generation_prompt}\n\n"
            "=== PLANO ANALÍTICO VALIDADO ===\n"
            f"{plan_context}\n"
            "=== FIM DO PLANO ANALÍTICO ===\n"
        )
        prompt = self._append_temporal_hint(prompt, temporal)
        messages = self._stage_messages(
            prompt,
            user_question,
            conversation_context,
        )
        try:
            response = self._chat(messages)
            raw_content = response.get("message", {}).get("content", "")
            return self._clean_sql_response(raw_content)
        except Exception as exc:
            if isinstance(exc, TranslationStageError):
                raise
            raise TranslationStageError("sql_generation", str(exc)) from exc

    def repair_query(
        self,
        sql: str,
        database_error: str,
        plan: object = None,
        user_question: str = "",
        conversation_context: Optional[Sequence[Dict[str, str]]] = None,
    ) -> dict:
        prompt = self.sql_generation_prompt or self.system_prompt
        plan_context = ""
        if isinstance(plan, Mapping):
            plan_context = json.dumps(
                dict(plan),
                ensure_ascii=False,
                sort_keys=True,
            )
        repair_prompt = (
            f"{prompt}\n\n"
            "=== REPARO ÚNICO DE SQL ===\n"
            f"SQL original:\n{sql}\n"
            f"Erro retornado pelo banco:\n{database_error}\n"
            f"Plano analítico original:\n{plan_context or 'não disponível'}\n"
            "Corrija somente o necessário, preserve a intenção e retorne "
            "o contrato JSON existente. Não retorne explicações."
        )
        messages = self._stage_messages(
            repair_prompt,
            user_question or "Corrija a consulta conforme o erro do banco.",
            conversation_context,
        )
        try:
            response = self._chat(messages)
            raw_content = response.get("message", {}).get("content", "")
            return self._clean_sql_response(raw_content)
        except Exception as exc:
            if isinstance(exc, TranslationStageError):
                raise
            raise TranslationStageError("repair", str(exc)) from exc

    def translate_to_sql(
        self,
        user_question: str,
        conversation_context: Optional[Sequence[Dict[str, str]]] = None,
    ) -> dict:
        """
        Envia a pergunta do usuário e o prompt de sistema para o modelo via Ollama,
        incluindo até seis turnos anteriores, e retorna SQL e configuração de gráfico.
        
        Args:
            user_question (str): A pergunta em linguagem natural do usuário.
            conversation_context: Mensagens anteriores em formato compatível com Ollama.
            
        Returns:
            dict: Objeto contendo chaves "sql" e "grafico".
        """
        if self.planner_prompt and self.sql_generation_prompt:
            temporal = TemporalInterpreter().interpret(
                user_question,
                date.today(),
            )
            plan = self.plan_question(
                user_question,
                conversation_context=conversation_context,
                temporal_interpretation=temporal,
            )
            try:
                translated = self.translate_plan_to_sql(
                    plan,
                    user_question,
                    conversation_context=conversation_context,
                    temporal_interpretation=temporal,
                )
            except QueryValidationError as exc:
                plan = self.plan_question(
                    user_question,
                    conversation_context=conversation_context,
                    temporal_interpretation=temporal,
                    planner_feedback=str(exc),
                )
                translated = self.translate_plan_to_sql(
                    plan,
                    user_question,
                    conversation_context=conversation_context,
                    temporal_interpretation=temporal,
                )
            translated["plan"] = plan.to_dict()
            translated["temporal"] = (
                temporal.planning_hint
                if temporal.planning_hint is not None
                else None
            )
            return translated

        return self._translate_legacy(
            user_question,
            conversation_context,
        )

    def _translate_legacy(
        self,
        user_question: str,
        conversation_context: Optional[Sequence[Dict[str, str]]] = None,
    ) -> dict:
        context_messages = list(conversation_context or ())[-12:]
        messages = [
            {"role": "system", "content": self.system_prompt},
            *context_messages,
            {"role": "user", "content": user_question}
        ]
        
        try:
            response = self._chat(messages)
            raw_content = response.get('message', {}).get('content', '')
            return self._clean_sql_response(raw_content)
        except Exception as e:
            raise RuntimeError(f"Erro ao comunicar com o Ollama: {e}")

    def _chat(
        self,
        messages: Sequence[Dict[str, str]],
    ) -> Mapping[str, Any]:
        if self.chat_client is not None:
            return self.chat_client(
                model=self.model_name,
                messages=messages,
            )
        return ollama.chat(model=self.model_name, messages=messages)

    @staticmethod
    def _stage_messages(
        prompt: str,
        user_question: str,
        conversation_context: Optional[Sequence[Dict[str, str]]],
    ) -> List[Dict[str, str]]:
        return [
            {"role": "system", "content": prompt},
            *list(conversation_context or ())[-12:],
            {"role": "user", "content": user_question},
        ]

    @staticmethod
    def _append_temporal_hint(
        prompt: str,
        temporal: TemporalInterpretation,
    ) -> str:
        if temporal.planning_hint is None:
            return prompt
        hint = json.dumps(
            temporal.planning_hint,
            ensure_ascii=False,
            sort_keys=True,
        )
        return f"{prompt}\n=== DICA TEMPORAL DETERMINÍSTICA ===\n{hint}"

    @staticmethod
    def _append_planner_feedback(
        prompt: str,
        feedback: Optional[str],
    ) -> str:
        if not feedback:
            return prompt
        return (
            f"{prompt}\n"
            "=== CORREÇÃO OBRIGATÓRIA DO PLANO ANTERIOR ===\n"
            "A tentativa anterior foi rejeitada pela validação do contrato ou "
            "do schema. Corrija o problema abaixo e retorne novamente somente "
            "o JSON do plano. Não repita identificadores que não aparecem no "
            "schema fornecido.\n"
            f"Problema: {feedback}\n"
        )


class TranslationStageError(RuntimeError):
    """Retryable failure from the planner or SQL-generation stage."""

    def __init__(self, stage: str, message: str):
        self.stage = stage
        self.retryable = True
        super().__init__(f"{stage} stage failed: {message}")
