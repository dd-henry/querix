# Ask SQL - Arquitetura e Funcionamento

Este documento detalha como a aplicação **Ask SQL** funciona, sua arquitetura e a responsabilidade de cada módulo.

## Visão Geral

O **Ask SQL** é uma aplicação web interativa que permite aos usuários conversar com um banco de dados relacional. Ele traduz perguntas em linguagem natural para consultas SQL nativas, executa essas consultas no banco de dados, exibe os resultados em formato tabular, fornece download em CSV e renderiza gráficos baseados nas recomendações da Inteligência Artificial.

A aplicação usa React + TypeScript no frontend, FastAPI no backend, um provedor LLM configurável (Ollama local ou Gemini via Google AI Studio) para processamento de linguagem natural, e **pandas** + **SQLAlchemy** para gestão dos dados.

## Estrutura do Código e Componentes Principais

O código é modular e segue o princípio de separação de responsabilidades.

### 1. Ponto de Entrada e Interface: `web/` e `api/`
- **`web/`:** Renderiza a aplicação React, mantém a transcrição estável e coordena autenticação, conversas, execução, resultados e histórico.
- **`api/`:** Expõe autenticação, conversas, tradução, execução e histórico. `app.py` e `components.py` permanecem como interface Streamlit legada durante a migração.

### 2. Motor de Tradução (LLM): `core/translator.py`
O **`Translator`** é responsável pela comunicação com o modelo de inteligência artificial através do cliente configurado em `core/llm.py`.
Ele não interage diretamente com o banco de dados nem reconhece entidades de negócio.
- Ele recebe a instrução do usuário em linguagem natural e sempre a encaminha ao modelo.
- Para uma conversa retomada, recebe também até seis turnos concluídos anteriores, com mensagens do usuário e do assistente, incluindo SQL e erros.
- Envia isso junto ao contexto (System Prompt) ao provedor selecionado por `LLM_PROVIDER`. O padrão local usa `qwen2.5-coder:7b`; o modo `google` usa o modelo definido em `GEMINI_MODEL`.
- Ele possui uma funcionalidade essencial de extração e limpeza: limpa as "tagarelices" comuns de respostas do LLM, extraindo apenas o JSON válido que deve conter a chave `sql` e, opcionalmente, as instruções do `grafico`.

### 3. Engenharia de Prompt: `core/prompter.py`
O **`Prompter`** gera o contexto necessário para que o LLM "entenda" como e de onde extrair os dados. Ele unifica quatro camadas de contexto em um *System Prompt*:
- **Estratégias de Funcionamento:** Define o tom de "Engenheiro de Dados Sênior", exige o retorno exclusivo em formato JSON, orienta a análise de medidas e dimensões e impede a invenção de entidades.
- **Esquema Ao Vivo (Live Schema):** Uma visualização atualizada das tabelas, colunas, comentários e chaves estrangeiras obtida diretamente do banco de dados relacional.
- **Contextos Arquivados:** Realiza a leitura e anexação de arquivos locais dentro de uma suposta pasta `context/`. Ele busca arquivos DDL (`.sql`) e regras de negócio (`.md`, `.txt`) embutindo as lógicas específicas da organização na memória de curto prazo do assistente.
- **Data de Referência:** Informa a data atual usada para interpretar períodos incompletos sem criar filtros temporais arbitrários.

O planejador é orientado pelo schema. Não há um construtor de SQL de vendas ou de qualquer outro nicho no código; nomes de tabelas, colunas, métricas e joins vêm do contexto carregado em runtime.

### 4. Integração com Banco de Dados: `database/base.py` e `database/postgres.py`
A comunicação com o banco de dados ocorre através do padrão *Adapter*.
- **`base.py`:** Define a Interface (`DatabaseAdapter`) usando a biblioteca abstrata `abc`. Garante que qualquer implementação futura de banco de dados terá de implementar métodos de conexão, teste, schema dinâmico e execução de query que retorne um `pd.DataFrame`.
- **`postgres.py`:** A implementação dedicada do PostgreSQL. 
  - Utiliza o `load_dotenv` para buscar as credenciais com segurança.
  - Usa o `SQLAlchemy` e o driver `psycopg2` para gerir conexões.
  - Possui o método `get_schema_info` que consulta o dicionário de dados interno do PostgreSQL (`information_schema` e `pg_catalog`) para extrair nomes, tipos, comentários e relacionamentos de chaves estrangeiras para entregar à IA.
  - Também fornece a execução em transação somente de leitura usada pelos retries de consulta.

### 5. Persistência de Conversas e Histórico

`ConversationRepository` cria e consulta as tabelas `ask_sql_conversation_sessions` e `ask_sql_conversation_messages`:

- Cada sessão tem um UUID, o `user_id` proprietário, título, estado de favorito e horários de criação e atividade. O proprietário referencia `auth.users`; as operações de listar, carregar, adicionar mensagem, favoritar e excluir filtram pelo usuário autenticado.
- Cada mensagem tem um ID ordenável, `request_id`, papel (`user` ou `assistant`), conteúdo, SQL, erro e metadados. A chave única `(session_id, request_id, role)` impede que um rerun grave novamente o mesmo lado do turno. Mensagens são excluídas em cascata com a sessão.
- O histórico `ask_sql_query_history` permanece separado e tem um `session_id` anulável com exclusão em cascata. Assim, consultas executadas podem ser acessadas pelo histórico próprio, enquanto registros legados sem sessão continuam sem vínculo.
- Linhas retornadas pelo banco não são gravadas nessas tabelas. Ao reabrir uma conversa, o SQL aparece sem resultados persistidos e o frontend oferece a ação `Reexecutar consulta` para buscar dados atuais.
- A listagem remove sessões não favoritas sem atividade há pelo menos um ano antes de apresentar as conversas do proprietário. Sessões favoritas não entram nessa limpeza.

## Fluxo Completo de Operação

1. **Setup e autenticação:** A API coleta o esquema, monta o prompt e inicializa o tradutor com o contexto atual. Após autenticação, o frontend apresenta um rascunho vazio e as conversas do usuário na barra lateral.
2. **Persistência do prompt:** Ao enviar a primeira pergunta, o app cria uma sessão titulada pelo prompt e salva a mensagem do usuário. Em sessões existentes, adiciona a mensagem à sessão ativa. A chave única por sessão, requisição e papel protege gravações contra duplicidade.
3. **Contexto e tradução:** O `ConversationRepository` busca até seis turnos concluídos da sessão ativa, em ordem cronológica. O tradutor envia esses pares, o schema contextual e a nova pergunta ao provedor LLM configurado. A resposta precisa usar apenas entidades declaradas nesse contexto.
4. **Revisão de SQL:** A revisão começa ativada. Nesse modo, o SQL é persistido na mensagem do assistente e exibido com uma ação de execução separada. Se a revisão estiver desativada, o app encaminha o SQL para execução direta.
5. **Execução e histórico:** O app consome a ação pendente uma vez, mostra o progresso e executa a consulta pelo `PostgresAdapter`. Em caso de sucesso, associa a consulta ao histórico e mantém o DataFrame no estado do Streamlit; não salva as linhas retornadas na conversa. Falhas persistem o SQL e o erro na mensagem do assistente.
6. **Renderização:** `render_chat_messages` percorre a transcrição persistida e renderiza cada mensagem uma vez. Resultados disponíveis na sessão recebem tabela, gráfico e download CSV; erros e SQL permanecem associados à mensagem correspondente.
7. **Retomada e retry:** Ao reabrir uma sessão, o repositório carrega as mensagens do proprietário em ordem e não restaura DataFrames. A ação `Reexecutar consulta` executa o SQL armazenado usando apenas os identificadores da conversa e da solicitação; o backend recupera e valida o SQL e o resultado atualiza a mesma mensagem do assistente. Um retry também atualiza a mesma mensagem e, para SQL, usa uma transação somente de leitura.
8. **Organização do workspace:** A conversa ocupa a área principal. A barra lateral reúne sessões, histórico de consultas, consultas compartilhadas e controles administrativos conforme o papel do usuário.