import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class Prompter:
    """
    Classe responsável por consolidar o contexto do banco de dados (DDLs) 
    e regras de negócio em um único System Prompt bem estruturado.
    """

    def __init__(self, context_dir: str = "context"):
        self.context_dir = Path(context_dir)
        self.ddls_dir = self.context_dir / "ddls"
        self.rules_dir = self.context_dir / "business_rules"

    def _read_directory_files(self, directory: Path, valid_extensions: tuple) -> str:
        """
        Lê e concatena o conteúdo de todos os arquivos de um diretório 
        que correspondam às extensões especificadas.
        """
        consolidated_content = []
        
        if not directory.exists():
            return ""

        for file_path in directory.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in valid_extensions:
                try:
                    with open(file_path, "r", encoding="utf-8") as file:
                        content = file.read().strip()
                        consolidated_content.append(f"-- Arquivo: {file_path.name} --\n{content}\n")
                except Exception as e:
                    logger.error(f"Erro ao ler arquivo {file_path.name}: {e}")

        return "\n".join(consolidated_content)

    def build_system_prompt(self, live_schema: str = "") -> str:
        """
        Gera a string final do System Prompt estruturando as instruções gerais,
        esquema atual lido do banco, DDLs e regras de negócio.
        """
        ddls_content = self._read_directory_files(self.ddls_dir, (".sql",))
        rules_content = self._read_directory_files(self.rules_dir, (".md", ".txt"))

        system_prompt = (
            "Você é um Engenheiro de Dados Sênior e Especialista em PostgreSQL.\n"
            "Sua única função é traduzir solicitações em linguagem natural para consultas SQL válidas.\n"
            "ATENÇÃO: Utilize estritamente sintaxe nativa do PostgreSQL. Para manipulação de datas, use EXTRACT(MONTH FROM coluna) ou EXTRACT(YEAR FROM coluna). NUNCA use funções genéricas como MONTH() ou YEAR().\n"
            "Se a pergunta exigir informações, tabelas ou colunas que não existem no ESQUEMA DO BANCO DE DADOS fornecido, não invente dados.\n"
            "Neste caso, retorne EXCLUSIVAMENTE a frase: 'AVISO: As informações solicitadas não existem no banco de dados.'\n"
            "Caso contrário, retorne EXCLUSIVAMENTE um objeto JSON válido com a seguinte estrutura:\n"
            "{\n"
            '  "sql": "código SQL puro",\n'
            '  "grafico": {\n'
            '    "tipo": "bar", // Pode ser "bar" (barras) ou "line" (linhas). Use null se não fizer sentido gerar um gráfico.\n'
            '    "eixo_x": "nome_da_coluna_x",\n'
            '    "eixo_y": "nome_da_coluna_y",\n'
            '    "titulo": "Título Sugerido para o Gráfico"\n'
            "  }\n"
            "}\n"
            "Não inclua blocos de formatação markdown (como ```json) ou qualquer texto adicional, apenas o JSON puro.\n\n"
        )

        if live_schema:
            system_prompt += "=== CONTEXTO: ESQUEMA ATUAL DO BANCO DE DADOS (Extraído do PostgreSQL) ===\n"
            system_prompt += f"{live_schema}\n"

        if ddls_content:
            system_prompt += "=== CONTEXTO: ESQUEMA DO BANCO DE DADOS (DDLs) ===\n"
            system_prompt += f"{ddls_content}\n"

        if rules_content:
            system_prompt += "=== CONTEXTO: REGRAS DE NEGÓCIO ===\n"
            system_prompt += f"{rules_content}\n"

        return system_prompt.strip()

# --- Exemplo de uso rápido (opcional, apenas para testes locais) ---
if __name__ == "__main__":
    prompter = Prompter()
    print(prompter.build_system_prompt())
