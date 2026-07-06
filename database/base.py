import abc
import pandas as pd

class DatabaseAdapter(abc.ABC):
    """
    Classe base abstrata para adaptadores de banco de dados.
    Define os métodos obrigatórios que qualquer banco de dados suportado deve implementar.
    """

    @abc.abstractmethod
    def connect(self):
        """Estabelece a conexão com o banco de dados."""
        pass

    @abc.abstractmethod
    def execute_query(self, sql: str) -> pd.DataFrame:
        """Executa uma instrução SQL e retorna os resultados como um DataFrame pandas."""
        pass

    @abc.abstractmethod
    def test_connection(self) -> bool:
        """Testa a conexão, retornando True se bem-sucedida, ou False caso contrário."""
        pass

    @abc.abstractmethod
    def get_schema_info(self) -> str:
        """Consulta as informações de esquema (tabelas, colunas e comentários) do banco real."""
        pass
