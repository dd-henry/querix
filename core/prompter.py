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
            "Sua única função é traduzir solicitações em linguagem natural para consultas SQL analíticas válidas.\n"
            "Pense como um analista de dados operacional: entregue métricas, dimensões, agrupamentos e filtros que respondam à intenção do usuário, sem inventar conclusões.\n"
            "ATENÇÃO: Utilize estritamente sintaxe nativa do PostgreSQL. Para filtrar períodos, use um intervalo inclusivo no início e exclusivo no fim (coluna >= início AND coluna < fim). Para agrupamentos mensais, use EXTRACT(MONTH FROM coluna) ou EXTRACT(YEAR FROM coluna). NUNCA use funções genéricas como MONTH() ou YEAR().\n"
            "REGRAS ANALÍTICAS DO DOMÍNIO DE VENDAS:\n"
            "- Considere apenas vendas com status = 'concluida', exceto quando o usuário pedir explicitamente vendas canceladas.\n"
            "- Faturamento de cupons usa SUM(vendas.valor_total). Não use esse campo para calcular valor por produto.\n"
            "- Vendas por produto exigem a relação vendas -> itens_venda -> produtos.\n"
            "- Quantidade por produto usa SUM(itens_venda.quantidade).\n"
            "- Valor por produto usa SUM(itens_venda.subtotal), que preserva o preço histórico do item.\n"
            "- Quando a pergunta pedir produtos vendidos, retorne uma linha por produto com produto, quantidade e valor, agrupando por produtos.id e produtos.nome.\n"
            "- Quando a pergunta pedir total, agregue o resultado em vez de retornar linhas brutas.\n"
            "- Uma pergunta com mês ou ano deve filtrar o período completo, incluindo o ano; não filtre somente pelo número do mês.\n"
            "- Se vendas.valor_total e a soma de itens_venda.subtotal forem usados na mesma análise, mantenha as métricas separadas e sinalize a possível divergência.\n"
            "Se a pergunta exigir informações, tabelas ou colunas que não existem no ESQUEMA DO BANCO DE DADOS fornecido, não invente dados.\n"
            "Neste caso, retorne EXCLUSIVAMENTE a frase: 'AVISO: As informações solicitadas não existem no banco de dados.'\n"
            "Caso contrário, retorne EXCLUSIVAMENTE um objeto JSON válido com a seguinte estrutura:\n"
            "{\n"
            '  "sql": "código SQL puro",\n'
            '  "parameters": {},\n'
            '  "supporting_queries": [\n'
            "    {\n"
            '      "key": "identificador_estavel",\n'
            '      "title": "Título da análise",\n'
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
            "tabelas e colunas presentes no esquema atual e relações existentes. "
            "Use parâmetros nomeados para períodos e filtros; não invente "
            "tabelas, colunas ou valores. Se não houver complemento confiável, "
            'retorne "supporting_queries": []. Não escreva conclusões numéricas '
            "no JSON; elas serão calculadas a partir das linhas retornadas.\n"
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
