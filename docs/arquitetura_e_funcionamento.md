# Ask SQL - Arquitetura e Funcionamento

Este documento detalha como a aplicação **Ask SQL** funciona, sua arquitetura e a responsabilidade de cada módulo.

## Visão Geral

O **Ask SQL** é uma aplicação web interativa que permite aos usuários conversar com um banco de dados relacional. Ele traduz perguntas em linguagem natural para consultas SQL nativas, executa essas consultas no banco de dados, exibe os resultados em formato tabular, fornece download em CSV e renderiza gráficos baseados nas recomendações da Inteligência Artificial.

A aplicação foi construída em Python utilizando o framework **Streamlit** para a interface do usuário, a API local do **Ollama** para processamento de linguagem natural, e **pandas** + **SQLAlchemy** para gestão dos dados.

## Estrutura do Código e Componentes Principais

O código é modular e segue o princípio de separação de responsabilidades.

### 1. Ponto de Entrada e Interface: `app.py` e `components.py`
- **`app.py`:** Configura a página, instancia serviços com cache, verifica o usuário autenticado e coordena conversas, estado transitório, tradução, execução e histórico. Uma conversa em branco só é persistida quando recebe o primeiro prompt.
- **`components.py`:** Renderiza a lista de mensagens do chat como uma única transcrição. SQL e erros pertencem à mensagem do assistente; tabelas, gráficos e downloads usam os resultados mantidos no estado da sessão do Streamlit. A revisão de SQL aparece em um cartão de ação separado, não como uma segunda mensagem.

### 2. Motor de Tradução (LLM): `core/translator.py`
O **`Translator`** é responsável pela comunicação com o modelo de inteligência artificial via biblioteca `ollama`. 
Ele não interage diretamente com o banco de dados. 
- Ele recebe a instrução do usuário em linguagem natural.
- Para uma conversa retomada, recebe também até seis turnos concluídos anteriores, com mensagens do usuário e do assistente, incluindo SQL e erros.
- Envia isso junto ao contexto (System Prompt) ao LLM local (o modelo definido no projeto é o `qwen2.5-coder:7b`).
- Ele possui uma funcionalidade essencial de extração e limpeza: limpa as "tagarelices" comuns de respostas do LLM, extraindo apenas o JSON válido que deve conter a chave `sql` e, opcionalmente, as instruções do `grafico`.

### 3. Engenharia de Prompt: `core/prompter.py`
O **`Prompter`** gera o contexto necessário para que o LLM "entenda" como e de onde extrair os dados. Ele unifica três camadas de contexto em um extenso *System Prompt*:
- **Regras de Funcionamento:** Define o tom de "Engenheiro de Dados Sênior", exige o retorno exclusivo em formato JSON e especifica sintaxes obrigatórias do PostgreSQL (como não usar `MONTH()`).
- **Esquema Ao Vivo (Live Schema):** Uma visualização atualizada das tabelas e colunas obtida diretamente do banco de dados relacional.
- **Contextos Arquivados:** Realiza a leitura e anexação de arquivos locais dentro de uma suposta pasta `context/`. Ele busca arquivos DDL (`.sql`) e regras de negócio (`.md`, `.txt`) embutindo as lógicas específicas da organização na memória de curto prazo do assistente.

### 4. Integração com Banco de Dados: `database/base.py` e `database/postgres.py`
A comunicação com o banco de dados ocorre através do padrão *Adapter*.
- **`base.py`:** Define a Interface (`DatabaseAdapter`) usando a biblioteca abstrata `abc`. Garante que qualquer implementação futura de banco de dados terá de implementar métodos de conexão, teste, schema dinâmico e execução de query que retorne um `pd.DataFrame`.
- **`postgres.py`:** A implementação dedicada do PostgreSQL. 
  - Utiliza o `load_dotenv` para buscar as credenciais com segurança.
  - Usa o `SQLAlchemy` e o driver `psycopg2` para gerir conexões.
  - Possui o método `get_schema_info` que faz uma consulta especial no dicionário de dados interno do PostgreSQL (`information_schema` e `pg_catalog`) para extrair não apenas nomes, mas também os comentários (metadados) das tabelas e colunas para entregar à IA.
  - Também fornece a execução em transação somente de leitura usada pelos retries de consulta.

### 5. Persistência de Conversas e Histórico

`ConversationRepository` cria e consulta as tabelas `ask_sql_conversation_sessions` e `ask_sql_conversation_messages`:

- Cada sessão tem um UUID, o `user_id` proprietário, título, estado de favorito e horários de criação e atividade. O proprietário referencia `auth.users`; as operações de listar, carregar, adicionar mensagem, favoritar e excluir filtram pelo usuário autenticado.
- Cada mensagem tem um ID ordenável, `request_id`, papel (`user` ou `assistant`), conteúdo, SQL, erro e metadados. A chave única `(session_id, request_id, role)` impede que um rerun grave novamente o mesmo lado do turno. Mensagens são excluídas em cascata com a sessão.
- O histórico `ask_sql_query_history` permanece separado e tem um `session_id` anulável com exclusão em cascata. Assim, consultas executadas podem ser acessadas pelo histórico próprio, enquanto registros legados sem sessão continuam sem vínculo.
- Linhas retornadas pelo banco não são gravadas nessas tabelas. O DataFrame existe apenas no estado transitório do Streamlit após a execução; ao reabrir uma conversa, o SQL aparece sem resultados e precisa ser executado explicitamente para buscar dados atuais.
- A listagem remove sessões não favoritas sem atividade há pelo menos um ano antes de apresentar as conversas do proprietário. Sessões favoritas não entram nessa limpeza.

## Fluxo Completo de Operação

1. **Setup e autenticação:** O `app.py` coleta o esquema, monta o prompt e inicializa o tradutor em recursos cacheados do Streamlit. Após autenticação, apresenta um rascunho vazio e as conversas do usuário na barra lateral.
2. **Persistência do prompt:** Ao enviar a primeira pergunta, o app cria uma sessão titulada pelo prompt e salva a mensagem do usuário. Em sessões existentes, adiciona a mensagem à sessão ativa. A chave única por sessão, requisição e papel protege gravações contra duplicidade.
3. **Contexto e tradução:** O `ConversationRepository` busca até seis turnos concluídos da sessão ativa, em ordem cronológica. O tradutor envia esses pares anteriores e o novo prompt ao Ollama.
4. **Revisão de SQL:** A revisão começa ativada. Nesse modo, o SQL é persistido na mensagem do assistente e exibido com uma ação de execução separada. Se a revisão estiver desativada, o app encaminha o SQL para execução direta.
5. **Execução e histórico:** O app consome a ação pendente uma vez, mostra o progresso e executa a consulta pelo `PostgresAdapter`. Em caso de sucesso, associa a consulta ao histórico e mantém o DataFrame no estado do Streamlit; não salva as linhas retornadas na conversa. Falhas persistem o SQL e o erro na mensagem do assistente.
6. **Renderização:** `render_chat_messages` percorre a transcrição persistida e renderiza cada mensagem uma vez. Resultados disponíveis na sessão recebem tabela, gráfico e download CSV; erros e SQL permanecem associados à mensagem correspondente.
7. **Retomada e retry:** Ao reabrir uma sessão, o repositório carrega as mensagens do proprietário em ordem e não restaura DataFrames. A execução de SQL anterior exige uma ação explícita. Um retry atualiza a mesma mensagem do assistente e, para SQL, usa uma transação somente de leitura.
8. **Organização do workspace:** A conversa ocupa a área principal. A barra lateral reúne sessões, histórico de consultas, consultas compartilhadas e controles administrativos conforme o papel do usuário.