import logging
import ollama

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

try:
    logger.info("Enviando pergunta para o Qwen 7B local...")
    
    # Atualizado com a tag :7b
    response = ollama.chat(model='qwen2.5-coder:7b', messages=[
        {
            'role': 'system',
            'content': 'Você é um assistente focado em banco de dados. Responda apenas com o código SQL puro.'
        },
        {
            'role': 'user',
            'content': 'Crie uma tabela chamada usuarios com id, nome e email.'
        }
    ])

    logger.info("\n--- Resposta do Modelo ---")
    logger.info(response['message']['content'])
    logger.info("--------------------------")

except Exception as e:
    logger.error(f"\nErro ao conectar com o Ollama: {e}")