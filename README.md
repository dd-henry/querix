# Ask-SQL 🤖

> Converse com seu banco de dados usando linguagem natural.

O **Ask-SQL** é uma ferramenta interativa que traduz perguntas em linguagem natural para consultas SQL, permitindo que você explore seus dados sem precisar escrever código SQL. A aplicação utiliza um modelo de linguagem local via **Ollama** para a tradução, se conecta a um banco de dados **PostgreSQL** para executar as consultas e exibe os resultados de forma amigável.

## ✨ Recursos

*   **Tradução de Linguagem Natural para SQL:** Faça perguntas como "quantos usuários se cadastraram no último mês?" e obtenha a consulta SQL correspondente.
*   **Execução Direta no Banco de Dados:** Conecta-se ao seu banco de dados PostgreSQL para executar as consultas geradas.
*   **Arquitetura Modular:** Código organizado em componentes com responsabilidades claras, facilitando a manutenção e extensão.
*   **Engenharia de Prompt Avançada:** Utiliza o esquema do banco de dados e regras de negócio customizadas para gerar prompts mais precisos.
*   **Suíte de Testes Abrangente:** Inclui testes unitários e de integração para garantir a qualidade e a confiabilidade do código.

## 🏗️ Arquitetura e Fluxo de Dados

O projeto é construído com uma arquitetura modular, garantindo que cada componente tenha uma única responsabilidade.

```mermaid
graph TD
    A[Usuário via Interface] --> B(app.py);
    B --> C{Prompter};
    D[Schema do Banco] --> C;
    E[Regras de Negócio] --> C;
    C --> F{Translator (Ollama)};
    F --> G[Consulta SQL Gerada];
    G --> H{Executor (Postgres)};
    H --> I[Resultados (DataFrame)];
    I --> B;
    B --> A;
```

1.  **Interface (`app.py` e `components.py`):** Ponto de entrada da aplicação. Gerencia a interface do usuário, o estado da sessão e o fluxo principal.
2.  **Engenharia de Prompt (`core/prompter.py`):** Monta o "System Prompt" que será enviado ao modelo de linguagem, unindo regras de negócio, o esquema do banco de dados e a pergunta do usuário.
3.  **Motor de Tradução (`core/translator.py`):** Comunica-se com a API do Ollama, enviando o prompt e tratando a resposta para extrair a consulta SQL do JSON retornado.
4.  **Banco de Dados (`database/postgres.py`):** Implementa a lógica de conexão com o PostgreSQL usando SQLAlchemy, executa a consulta e retorna os resultados como um DataFrame do pandas.

## 🚀 Instalação e Configuração

Siga os passos abaixo para configurar o ambiente de desenvolvimento.

1.  **Clone o repositório:**
    ```bash
    git clone <url-do-seu-repositorio>
    cd ask-sql
    ```

2.  **Crie e ative um ambiente virtual:**
    ```bash
    python -m venv venv
    source venv/bin/activate
    ```

3.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure as variáveis de ambiente:**
    Crie um arquivo `.env` na raiz do projeto e adicione as credenciais do seu banco de dados e a URL do Ollama.
    ```env
    DB_HOST=localhost
    DB_PORT=5432
    DB_USER=seu_usuario
    DB_PASSWORD=sua_senha
    DB_NAME=seu_banco
    OLLAMA_API_URL=http://localhost:11434
    ```

## 🏃 Como Usar

Para executar a aplicação principal, use o `app.py`. A interface será aberta no seu navegador.

```bash
streamlit run app.py
```

Você também pode executar uma pergunta diretamente pela linha de comando para testes rápidos:

```bash
python app.py "Sua pergunta em linguagem natural aqui"
```

**Exemplo:**

```bash
python app.py "Quantos usuários se cadastraram no último mês?"
```

## ✅ Estratégia de Testes

O projeto utiliza `pytest` para garantir a qualidade do código, com uma clara separação entre testes unitários e de integração.

### Testes Unitários
Valida a lógica interna dos componentes de forma isolada, usando *mocks* para simular dependências externas.

-   **`test_prompter.py`:** Garante que o montador de prompts anexa corretamente as regras e o esquema do banco.
-   **`test_translator.py`:** Valida a extração do JSON da resposta do modelo de linguagem, mesmo com ruídos.
-   **`test_postgres.py`:** Assegura que o adaptador do banco de dados se comporta como esperado sem a necessidade de uma conexão real.

### Testes de Integração
Valida o fluxo completo, envolvendo a comunicação real com a API do Ollama.

-   **`test_integration_ollama.py`:** Envia uma requisição real para o modelo de linguagem e verifica se a resposta contém a estrutura esperada (uma consulta SQL válida).

### Executando os Testes

Graças às configurações no arquivo `pytest.ini`, você pode executar diferentes suítes de teste:

-   **Rodar todos os testes:**
    ```bash
    pytest -v
    ```
-   **Rodar apenas testes unitários (Rápidos):**
    ```bash
    pytest -m "not integration" -v
    ```
-   **Rodar apenas testes de integração (Lentos, requer Ollama):**
    ```bash
    pytest -m "integration" -v
    ```

