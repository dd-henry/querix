import logging
from database.postgres import PostgresAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def testar():
    logger.info("Iniciando teste de conexão com o banco de dados...")
    adapter = PostgresAdapter()
    
    sucesso = adapter.test_connection()
    
    if sucesso:
        logger.info("✅ Conexão estabelecida com sucesso! O banco está operante.")
    else:
        logger.error("❌ Falha ao conectar no banco de dados. Verifique suas credenciais no .env.")

if __name__ == "__main__":
    testar()
