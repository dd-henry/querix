import os
import logging
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from database.base import DatabaseAdapter

logger = logging.getLogger(__name__)

class PostgresAdapter(DatabaseAdapter):
    """
    Adaptador para conexão e execução de queries em um banco de dados PostgreSQL.
    As credenciais devem ser fornecidas via variáveis de ambiente (.env).
    """

    def __init__(self):
        # Carrega variáveis de ambiente do arquivo .env
        load_dotenv()
        
        self.database_url = os.getenv("DATABASE_URL")
        self.host = os.getenv("POSTGRES_HOST")
        self.port = os.getenv("POSTGRES_PORT", "5432")
        self.user = os.getenv("POSTGRES_USER")
        self.password = os.getenv("POSTGRES_PASSWORD")
        self.dbname = os.getenv("POSTGRES_DBNAME")
        
        self.engine = None

    def connect(self):
        """Estabelece a conexão com o banco de dados PostgreSQL usando SQLAlchemy."""
        if not self.engine:
            if self.database_url:
                # Adapta a URL para usar o driver psycopg2 explicitamente exigido pelo SQLAlchemy
                connection_url = self.database_url.replace("postgresql://", "postgresql+psycopg2://")
            else:
                if not all([self.host, self.user, self.password, self.dbname]):
                     raise ValueError("Faltam variáveis de ambiente para a conexão com o banco de dados PostgreSQL.")
                
                # Usando psycopg2 como driver, que já está no requirements.txt
                connection_url = f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}"
                
            self.engine = create_engine(connection_url)

    def execute_query(self, sql: str, params=None) -> pd.DataFrame:
        """Executa uma query no PostgreSQL e retorna um DataFrame com os resultados."""
        self.connect()
        try:
            # No Pandas 2+, recomenda-se passar uma conexão do SQLAlchemy explicitamente
            with self.engine.connect() as connection:
                if params is None:
                    df = pd.read_sql(text(sql), connection)
                else:
                    df = pd.read_sql(text(sql), connection, params=params)
            return df
        except Exception as e:
            raise RuntimeError(f"Erro ao executar a query no PostgreSQL: {e}")

    def execute_read_only_query(self, sql: str, params=None) -> pd.DataFrame:
        """Executa uma consulta dentro de uma transação PostgreSQL somente leitura."""
        self.connect()
        try:
            with self.engine.connect() as connection:
                with connection.begin():
                    connection.execute(text("SET TRANSACTION READ ONLY"))
                    return pd.read_sql(text(sql), connection, params=params or {})
        except Exception as e:
            raise RuntimeError(f"Erro ao executar a query no PostgreSQL: {e}")

    def execute_command(self, sql: str, params=None):
        """Executa um comando transacional sem retornar um DataFrame."""
        self.connect()
        try:
            with self.engine.begin() as connection:
                result = connection.execute(text(sql), params or {})
                return result.rowcount
        except Exception as e:
            raise RuntimeError(f"Erro ao executar comando no PostgreSQL: {e}")

    def test_connection(self) -> bool:
        """Testa se a comunicação com o PostgreSQL está operante."""
        try:
            self.connect()
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Falha na conexão com o banco de dados: {e}")
            return False

    def get_schema_info(self) -> str:
        """Consulta metadados atuais do schema public e formata para a IA."""
        sql = """
        SELECT
            cols.table_name,
            (SELECT pg_catalog.obj_description(c.oid, 'pg_class')
             FROM pg_catalog.pg_class c
             WHERE c.relname = cols.table_name
               AND c.relnamespace = (SELECT oid FROM pg_catalog.pg_namespace WHERE nspname = 'public')
            ) AS table_comment,
            cols.column_name,
            cols.data_type,
            (SELECT pg_catalog.col_description(c.oid, cols.ordinal_position::int)
             FROM pg_catalog.pg_class c
             WHERE c.relname = cols.table_name
               AND c.relnamespace = (SELECT oid FROM pg_catalog.pg_namespace WHERE nspname = 'public')
            ) AS column_comment
        FROM
            information_schema.columns cols
        WHERE
            cols.table_schema = 'public'
        ORDER BY
            cols.table_name, cols.ordinal_position;
        """
        try:
            df = self.execute_query(sql)
            if df.empty:
                return "Nenhuma tabela encontrada no schema public."

            schema_text = []
            for table_name, group in df.groupby('table_name'):
                table_comment = group['table_comment'].iloc[0]
                comment_str = f" -- Comentário: {table_comment}" if pd.notna(table_comment) and table_comment else ""
                schema_text.append(f"Tabela: {table_name}{comment_str}")
                for _, row in group.iterrows():
                    col_comment = row['column_comment']
                    col_comment_str = f" -- Comentário: {col_comment}" if pd.notna(col_comment) and col_comment else ""
                    schema_text.append(f"  - {row['column_name']} ({row['data_type']}){col_comment_str}")
                schema_text.append("")

            relationships = self.execute_query(
                """
                SELECT
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                  ON tc.constraint_name = ccu.constraint_name
                 AND tc.table_schema = ccu.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = 'public'
                ORDER BY
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_name,
                    ccu.column_name;
                """
            )
            if not relationships.empty:
                schema_text.append("Relacionamentos (chaves estrangeiras):")
                for _, row in relationships.iterrows():
                    schema_text.append(
                        "  - "
                        f"{row['table_name']}.{row['column_name']} -> "
                        f"{row['foreign_table_name']}."
                        f"{row['foreign_column_name']}"
                    )

            return "\n".join(schema_text)
        except Exception as e:
            return f"Erro ao obter esquema: {e}"
