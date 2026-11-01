import re
import json
from collections.abc import Mapping
from typing import Dict, List, Optional, Sequence

import ollama


class Translator:
    """
    Motor de tradução que utiliza a API local do Ollama para converter
    linguagem natural em consultas SQL.
    """

    def __init__(self, system_prompt: str, model_name: str = "qwen2.5-coder:7b"):
        """
        Inicializa o tradutor com o prompt de sistema configurado e o modelo desejado.
        
        Args:
            system_prompt (str): O contexto consolidado de banco de dados e regras de negócio.
            model_name (str): O nome do modelo LLM local gerenciado pelo Ollama (ex: llama3).
        """
        self.system_prompt = system_prompt
        self.model_name = model_name

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
        context_messages = list(conversation_context or ())[-12:]
        messages = [
            {"role": "system", "content": self.system_prompt},
            *context_messages,
            {"role": "user", "content": user_question}
        ]
        
        try:
            response = ollama.chat(model=self.model_name, messages=messages)
            raw_content = response.get('message', {}).get('content', '')
            return self._clean_sql_response(raw_content)
        except Exception as e:
            raise RuntimeError(f"Erro ao comunicar com o Ollama: {e}")
