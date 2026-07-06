import re
import json
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
                return json.loads(json_str)
            except json.JSONDecodeError:
                raise ValueError(f"O modelo não retornou um JSON válido. Retorno isolado: {json_str}")
        else:
            raise ValueError("Não foi possível encontrar um objeto JSON válido na resposta do modelo.")

    def translate_to_sql(self, user_question: str) -> dict:
        """
        Envia a pergunta do usuário e o prompt de sistema para o modelo via Ollama,
        e retorna o dicionário com SQL e configuração de gráfico.
        
        Args:
            user_question (str): A pergunta em linguagem natural do usuário.
            
        Returns:
            dict: Objeto contendo chaves "sql" e "grafico".
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_question}
        ]
        
        try:
            response = ollama.chat(model=self.model_name, messages=messages)
            raw_content = response.get('message', {}).get('content', '')
            return self._clean_sql_response(raw_content)
        except Exception as e:
            raise RuntimeError(f"Erro ao comunicar com o Ollama: {e}")
