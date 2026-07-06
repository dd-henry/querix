# Ask SQL - Arquitetura e Funcionamento

Este documento detalha como a aplicação **Ask SQL** funciona, sua arquitetura e a responsabilidade de cada módulo.

## Visão Geral

O **Ask SQL** é uma aplicação web interativa que permite aos usuários conversar com um banco de dados relacional. Ele traduz perguntas em linguagem natural para consultas SQL nativas, executa essas consultas no banco de dados, exibe os resultados em formato tabular, fornece download em CSV e renderiza gráficos baseados nas recomendações da Inteligência Artificial.

A aplicação foi construída em Python utilizando o framework **Streamlit** para a interface do usuário, a API local do **Ollama** para processamento de linguagem natural, e **pandas** + **SQLAlchemy** para gestão dos dados.

## Estrutura do Código e Componentes Principais

O código é modular e segue o princípio de separação de responsabilidades.

### 1. Ponto de Entrada e Interface: `app.py` e `components.py`
- **`app.py`:** É o arquivo principal. Ele configura a página Streamlit, instancia os serviços (com cache para performance) e gerencia o estado da sessão (histórico de chat, requisições de gráficos e queries em estado de revisão). Todo o fluxo principal de entrada de texto e chamadas aos módulos secundários ocorre aqui.
- **`components.py`:** Isola as funções de renderização do Streamlit. Contém a lógica de desenhar o chat, renderizar DataFrames, disponibilizar os botões para download em CSV e instanciar dinamicamente gráficos recomendados pelo LLM. Também lida com a exibição da consulta pendente ("SQL gerado aguardando revisão").

### 2. Motor de Tradução (LLM): `core/translator.py`
O **`Translator`** é responsável pela comunicação com o modelo de inteligência artificial via biblioteca `ollama`. 
Ele não interage diretamente com o banco de dados. 
- Ele recebe a instrução do usuário em linguagem natural.
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

## Fluxo Completo de Operação

1. **Setup e Caching:** Ao iniciar, o `app.py` coleta o esquema do banco, o consolida via `Prompter` e o entrega para instanciar o `Translator`. Esses serviços rodam no cache do Streamlit (`@st.cache_resource`).
2. **Entrada do Usuário:** O usuário envia uma pergunta pelo chat do Streamlit.
3. **Tradução:** O `Translator` envia a pergunta ao Ollama. A LLM avalia a pergunta frente às tabelas existentes no sistema. Se for viável, ela devolve o SQL e uma formatação de gráfico encapsulados em JSON. 
4. **Revisão:** Com a opção de "Revisar" ativa (via toggle), a query SQL gerada entra na área de stand-by (`render_pending_sql`), esperando o usuário aprovar e clicar em "Executar Query".
5. **Execução:** O aplicativo usa o `PostgresAdapter` para executar o SQL cru gerado pela máquina diretamente no banco de dados e retorna o resultado formatado em um Pandas DataFrame.
6. **Resposta e Exibição:** O `app.py` alimenta o histórico (`session_state.messages`) e o Streamlit renderiza a resposta no chat (via `components.py`), mostrando a tabela e oferecendo o botão interativo do gráfico quando ele é sinalizado pela IA. Se houver erro, a exceção é tratada e exposta na tela de forma contida.