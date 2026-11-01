import logging
from datetime import date
from pathlib import Path
from typing import Optional

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

    def build_system_prompt(
        self,
        live_schema: str = "",
        reference_date: Optional[date] = None,
        sql_dialect: str = "PostgreSQL",
    ) -> str:
        """
        Gera a string final do System Prompt estruturando as instruções gerais,
        esquema atual lido do banco, DDLs e regras de negócio.
        """
        ddls_content = self._read_directory_files(self.ddls_dir, (".sql",))
        rules_content = self._read_directory_files(self.rules_dir, (".md", ".txt"))
        period_reference = reference_date or date.today()

        system_prompt = (
            "Você é um Engenheiro de Dados Sênior e Especialista em "
            f"{sql_dialect}.\n"
            "Sua única função é traduzir solicitações em linguagem natural "
            "para consultas SQL analíticas válidas.\n"
            "Use o contexto fornecido como fonte de verdade. Antes de escrever "
            "SQL, identifique as entidades, colunas, tipos, medidas, "
            "dimensões e relacionamentos disponíveis.\n"
            "REGRAS DE RACIOCÍNIO ANALÍTICO:\n"
            "- Use somente tabelas, colunas e relacionamentos declarados no "
            "contexto atual. Nunca invente identificadores.\n"
            "- Faça joins somente por chaves ou relacionamentos indicados no "
            "schema, DDL ou regras de negócio.\n"
            "- Escolha dimensões e medidas que respondam ao pedido. Quando "
            "houver relação confiável, complemente a resposta com até três "
            "leituras gerenciais úteis, sem substituir o resultado principal.\n"
            "- Agregue quando o usuário pedir totais, comparações, evolução "
            "ou rankings; preserve o nível de detalhe quando ele for pedido.\n"
            "- Para períodos explícitos, use a coluna temporal compatível com "
            "o tipo e a semântica disponíveis. Prefira intervalo inclusivo "
            "no início e exclusivo no fim (coluna >= início AND coluna < fim).\n"
            "- Se um mês for informado sem ano, use o ano da data de "
            "referência fornecida. Se não houver período explícito, não "
            "invente um filtro temporal, exceto quando o pedido significar "
            "explicitamente o período atual.\n"
            f"- Data de referência para períodos incompletos: "
            f"{period_reference.isoformat()}.\n"
            "- Retorne métricas calculadas somente por SQL executável e não "
            "escreva conclusões numéricas que não estejam no resultado.\n"
            "Se a pergunta exigir informações, tabelas ou colunas que não existem no ESQUEMA DO BANCO DE DADOS fornecido, não invente dados.\n"
            "Neste caso, retorne EXCLUSIVAMENTE a frase: 'AVISO: As informações solicitadas não existem no banco de dados.'\n"
            "Caso contrário, retorne EXCLUSIVAMENTE um objeto JSON válido com a seguinte estrutura:\n"
            "{\n"
            '  "sql": "código SQL puro",\n'
            '  "parameters": {},\n'
            '  "supporting_queries": [\n'
            "    {\n"
            '      "key": "identificador_estavel",\n'
            '      "title": "Título da leitura",\n'
            '      "sql": "SQL complementar somente leitura",\n'
            '      "parameters": {}\n'
            "    }\n"
            "  ],\n"
            '  "grafico": {\n'
            '    "tipo": "bar", // Pode ser "bar" (barras) ou "line" (linhas). Use null se não fizer sentido gerar um gráfico.\n'
            '    "eixo_x": "nome_da_coluna_x",\n'
            '    "eixo_y": "nome_da_coluna_y",\n'
            '    "titulo": "Título Sugerido para o Gráfico"\n'
            "  }\n"
            "}\n"
            "Use no máximo três supporting_queries. Cada uma deve usar somente "
            "tabelas, colunas, tipos e relações presentes no contexto atual. "
            "Use parâmetros nomeados para períodos e filtros; não invente "
            "valores. Se não houver complemento confiável, retorne "
            '"supporting_queries": [].\n'
            "Não inclua blocos de formatação markdown (como ```json) ou qualquer texto adicional, apenas o JSON puro.\n\n"
        )

        if live_schema:
            system_prompt += "=== CONTEXTO: ESQUEMA ATUAL DO BANCO DE DADOS ===\n"
            system_prompt += f"{live_schema}\n"

        if ddls_content:
            system_prompt += "=== CONTEXTO: ESQUEMA DO BANCO DE DADOS (DDLs) ===\n"
            system_prompt += f"{ddls_content}\n"

        if rules_content:
            system_prompt += "=== CONTEXTO: REGRAS DE NEGÓCIO ===\n"
            system_prompt += f"{rules_content}\n"

        return system_prompt.strip()

    def build_planner_prompt(
        self,
        live_schema: str = "",
        reference_date: Optional[date] = None,
        sql_dialect: str = "PostgreSQL",
    ) -> str:
        """Builds the stage prompt that extracts intent before SQL generation."""
        return (
            self.build_system_prompt(
                live_schema=live_schema,
                reference_date=reference_date,
                sql_dialect=sql_dialect,
            )
            + "\n\n"
            "=== ETAPA 1: PLANEJAMENTO ANALÍTICO ===\n"
            "Antes de escrever SQL, retorne somente um objeto JSON válido com "
            "intent, tables, relationships, dimensions, metrics, filters, "
            "grain e assumptions. Use arrays vazios quando uma categoria não "
            "for necessária. intent deve ser uma descrição curta e não vazia. "
            "assumptions deve conter pelo menos uma frase, "
            "mesmo quando a conclusão for que não há suposições adicionais.\n"
            "Não inclua SQL, markdown ou texto fora do JSON."
        )

    def build_sql_generation_prompt(
        self,
        live_schema: str = "",
        reference_date: Optional[date] = None,
        sql_dialect: str = "PostgreSQL",
    ) -> str:
        """Builds the stage prompt that renders SQL from a normalized plan."""
        return (
            self.build_system_prompt(
                live_schema=live_schema,
                reference_date=reference_date,
                sql_dialect=sql_dialect,
            )
            + "\n\n"
            "=== ETAPA 2: GERAÇÃO SQL ===\n"
            "Receba o plano analítico validado no contexto da mensagem. Gere "
            "SQL somente com identificadores presentes no esquema e preserve "
            "as dimensões, métricas, filtros, granularidade e período do plano. "
            "Retorne o contrato JSON existente com sql, parameters, "
            "supporting_queries e grafico. Não invente conclusões numéricas."
        )

# --- Exemplo de uso rápido (opcional, apenas para testes locais) ---
if __name__ == "__main__":
    prompter = Prompter()
    print(prompter.build_system_prompt())
