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

    def execute_query(self, sql: str) -> pd.DataFrame:
        """Executa uma query no PostgreSQL e retorna um DataFrame com os resultados."""
        self.connect()
        try:
            # No Pandas 2+, recomenda-se passar uma conexão do SQLAlchemy explicitamente
            with self.engine.connect() as connection:
                df = pd.read_sql(text(sql), connection)
            return df
        except Exception as e:
            raise RuntimeError(f"Erro ao executar a query no PostgreSQL: {e}")

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
        """Consulta tabelas, colunas, tipos e comentários do schema public e formata para a IA."""
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
            return "\n".join(schema_text)
        except Exception as e:
            return f"Erro ao obter esquema: {e}"
