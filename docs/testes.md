# Ask SQL - Estratégia de Testes

Este documento descreve como a qualidade do código da aplicação **Ask SQL** é mantida. O ecossistema de testes do projeto baseia-se no framework **pytest** e faz uso intensivo de *mocks* e *fixtures* para garantir estabilidade, confiabilidade, e viabilizar testes independentes em módulos complexos.

## Fluxos Cobertos e Divisão dos Testes

O projeto adota uma abordagem mista de testes, dividindo as baterias entre **Testes Unitários** (isolados e de execução rápida) e **Testes de Integração** (lentos, envolvendo agentes externos). Além disso, há módulos auxiliares de validação manual.

### 1. Testes Unitários

Estes testes validam lógicas internas sem envolver dependências externas, como bancos de dados em execução ou servidores locais de IA.

#### Regressões de conversas e UX

Os fluxos de conversa usam serviços externos simulados para que os testes validem estado e comportamento sem conectar a um PostgreSQL ou Ollama real:

- **`test_conversations.py`:** verifica escopo por proprietário, gravação idempotente e ordenada, falhas de persistência, favoritos, expiração, exclusão e o limite de seis turnos, incluindo a exclusão do turno em retry do contexto.
- **`test_query_history.py`:** verifica o vínculo anulável da conversa, exclusão em cascata, deduplicação dentro de cada sessão e compatibilidade com registros legados sem sessão.
- **`test_translator.py` e `test_llm.py`:** verificam contexto em ordem, limite de seis turnos, comportamento com contexto ausente ou vazio, seleção do provedor, adaptação do payload do Gemini e erros do LLM.
- **`test_postgres.py`:** verifica o uso de transações somente de leitura no retry e o retorno da contagem de linhas dos comandos.

Para executar os testes focados nesses fluxos:

```bash
python -m pytest test_conversations.py test_query_history.py test_translator.py test_llm.py test_postgres.py -q
```

#### Testes do Prompter (`test_prompter.py`)
Foca em garantir que o montador de prompts está anexando de forma correta as regras e informações dinâmicas do ambiente. 
- **Estratégias:** É utilizada a fixture nativa `tmp_path` do pytest para gerar árvores de pastas temporárias em memória, simulando diretórios de DDLs e de Regras de Negócio, avaliando se a injeção do texto desses arquivos de texto no corpo do "System Prompt" ocorre de modo seguro e completo. 

#### Testes do Extrator JSON / Translator (`test_translator.py`)
Garante que a classe capaz de decodificar as repostas do LLM é flexível o suficiente.  
- **Estratégias:** Uso de _Fixtures_ para recriar o tradutor.
- **Fluxos:**
  - Extração limpa, com o modelo retornando o JSON exato e estrito.
  - Isolamento de "sujeira", certificando-se de que se o LLM "tagarelar" usando blocos de código Markdown (```json) o sistema não corrompa a resposta, ignorando tudo o que estiver fora do bloco estruturado.
  - Retorno de erro (`pytest.raises`) ao tentar ler uma string sem um JSON formatado validamente.

#### Testes de Banco de Dados (`test_postgres.py`)
Garante que a biblioteca do banco se comporta como esperado ao receber credenciais e instanciar o SQLAlchemy.
- **Estratégias de Mocking:** O objetivo vital aqui é não usar um banco real para testes rápidos. O pacote utiliza `unittest.mock` (via `patch` e `MagicMock`) e a fixture de ambiente `monkeypatch` do pytest.
- **Fluxos:**
  - `monkeypatch` sobrecarrega a chamada do pacote `python-dotenv` garantindo que as credenciais provêm estritamente das simulações da suíte de teste e não do seu `.env` local.
  - A camada de conexão e a camada do *pandas* (`pd.read_sql`) foram completamente "mockadas" (*patched*). Em vez de bater no banco, o teste injeta um DataFrame sintético que confirma se o adaptador devolve a estrutura desejada sem executar instruções SQL reais.
  - Fazer os "caminhos infelizes" falharem graciosamente (simulando falha do mock no `test_connection()` para garantir que retorne booleano `False` sem interromper a API).

### 2. Testes de Integração e do LLM

O grande desafio de aplicações que envolvem IA Generativa é o seu não-determinismo. As strings devolvidas por modelos mudam sempre, impossibilitando verificações idênticas (`assert result == "..."`).

#### O Teste do Ollama (`test_integration_ollama.py`)
Este não é um teste mockado, ele realmente inicia a conexão com a API local do servidor **Ollama** chamando o modelo configurado em `OLLAMA_MODEL` (por padrão, `qwen2.5-coder:7b`). Os testes unitários do Gemini usam a API simulada e não enviam a chave para serviços externos.

- **Marcação e Isolamento:** Este teste é marcado intencionalmente com um decorador `@pytest.mark.integration`. Como a requisição para o LLM real pode demorar muitos segundos, ela pode ser ignorada no CI regular e disparada unicamente em *pipelines* específicas.
- **A Estratégia de Asserção Comportamental:** Ao invés de avaliar se a *string* produzida é idêntica a um template predefinido, o teste avalia *comportamentos*. 
  - A requisição pede uma consulta sobre "usuários". 
  - O teste confere se o JSON tem de fato as estruturas mapeadas (a chave `'sql'`).
  - O teste faz uma checagem elástica observando se a palavra `SELECT` e o alvo correto (`USUARIOS`) foram inferidos no campo de sql gerado dentro do dicionário.

## Executando os Testes

Para executar a suíte de testes, utilizamos o framework `pytest` a partir da raiz do projeto. Graças às configurações no arquivo `pytest.ini`, podemos separar a execução entre testes rápidos e lentos:

- **Regressão recomendada (fora de integração):** `python -m pytest -m "not integration" -q`
- **Rodar todos os testes, incluindo integrações:** `python -m pytest -q`
- **Rodar apenas testes de integração com Ollama:** `python -m pytest -m integration -q`

O gate completo de regressão também verifica a sintaxe Python antes dos testes:

```bash
python -m compileall -q api core database test_*.py
python -m pytest -m "not integration" -q
```

## Debugando os Testes

Como não é trivial prever 100% da saída de um LLM, o debug costuma ser parte frequente da manutenção:
- **Usando `print()`:** Por padrão, o `pytest` "engole" saídas de print. Para visualizar no terminal (por exemplo, visualizar o DDL em texto puro sendo enviado à IA), adicione a flag `-s` na execução: `pytest -s`.
- **Modo Interativo (PDB):** Adicione a função nativa `breakpoint()` em qualquer lugar do arquivo de teste. A execução será congelada naquele ponto, permitindo que você inspecione as variáveis (`resultado`, `prompt`, etc) em tempo real pelo terminal.

### 3. Validações Manuais ("Scripts de Fumaça")

O projeto inclui pequenos scripts isolados — `teste_db.py` e `teste_ollama.py`. 
Eles não utilizam asserções do pytest. Servem como scripts *CLI* rápidos para testar a infraestrutura local se algo falhar na subida da API (ex: "As credenciais do `.env` e o banco Postgres local estão atrelados de fato?" ou "A rede do Ollama está rodando e consegue devolver um SQL simples no terminal?").