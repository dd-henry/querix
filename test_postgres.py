import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from database.postgres import PostgresAdapter

@pytest.fixture
def mock_env(monkeypatch):
    """Configura variáveis de ambiente falsas antes de cada teste."""
    # Evita que o load_dotenv leia o arquivo .env real e sobrescreva o nosso mock
    monkeypatch.setattr("database.postgres.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_USER", "test_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_pass")
    monkeypatch.setenv("POSTGRES_DBNAME", "test_db")
    # Limpa a URL para forçar o uso das credenciais isoladas acima
    monkeypatch.delenv("DATABASE_URL", raising=False)

def test_connect_cria_engine_corretamente(mock_env):
    """Testa se a URL de conexão do SQLAlchemy é montada perfeitamente."""
    adapter = PostgresAdapter()
    
    with patch("database.postgres.create_engine") as mock_create_engine:
        adapter.connect()
        mock_create_engine.assert_called_once_with(
            "postgresql+psycopg2://test_user:test_pass@localhost:5432/test_db"
        )

def test_execute_query_retorna_dataframe(mock_env):
    """Testa a execução simulada de uma query retornando um DataFrame."""
    adapter = PostgresAdapter()
    fake_df = pd.DataFrame({"id": [1, 2], "nome": ["João", "Maria"]})
    
    # Intercepta as funções reais de banco do SQLAlchemy/Pandas
    with patch("database.postgres.create_engine"):
        with patch("database.postgres.pd.read_sql", return_value=fake_df) as mock_read_sql:
            
            df_resultado = adapter.execute_query("SELECT * FROM clientes")
            
            assert not df_resultado.empty
            assert len(df_resultado) == 2
            assert df_resultado.iloc[0]["nome"] == "João"

def test_test_connection_falha_graciosamente():
    """Garante que a função test_connection() captura erros e retorna False, em vez de estourar a aplicação."""
    adapter = PostgresAdapter()
    
    # Forçamos o connect a estourar um erro para simular banco offline
    with patch.object(adapter, "connect", side_effect=Exception("Banco de dados indisponível")):
        assert adapter.test_connection() is False