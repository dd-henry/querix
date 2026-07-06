# Ask SQL - Estratégia de Testes

Este documento descreve como a qualidade do código da aplicação **Ask SQL** é mantida. O ecossistema de testes do projeto baseia-se no framework **pytest** e faz uso intensivo de *mocks* e *fixtures* para garantir estabilidade, confiabilidade, e viabilizar testes independentes em módulos complexos.

## Fluxos Cobertos e Divisão dos Testes

O projeto adota uma abordagem mista de testes, dividindo as baterias entre **Testes Unitários** (isolados e de execução rápida) e **Testes de Integração** (lentos, envolvendo agentes externos). Além disso, há módulos auxiliares de validação manual.

### 1. Testes Unitários

Estes testes validam lógicas internas sem envolver dependências externas, como bancos de dados em execução ou servidores locais de IA.

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
  - Fazer os "caminhos infelizes" falharem graciosamente (simulando falha do mock no `test_connection()` para garantir que retorne booleano `False` invés de derrubar o Streamlit com uma `Exception` fatal).

### 2. Testes de Integração e do LLM (Ollama)

O grande desafio de aplicações que envolvem IA Generativa é o seu não-determinismo. As strings devolvidas por modelos mudam sempre, impossibilitando verificações idênticas (`assert result == "..."`).

#### O Teste do Ollama (`test_integration_ollama.py`)
Este não é um teste mockado, ele realmente inicia a conexão com a API local do servidor **Ollama** chamando o modelo `qwen2.5-coder:7b`.

- **Marcação e Isolamento:** Este teste é marcado intencionalmente com um decorador `@pytest.mark.integration`. Como a requisição para o LLM real pode demorar muitos segundos, ela pode ser ignorada no CI regular e disparada unicamente em *pipelines* específicas.
- **A Estratégia de Asserção Comportamental:** Ao invés de avaliar se a *string* produzida é idêntica a um template predefinido, o teste avalia *comportamentos*. 
  - A requisição pede uma consulta sobre "usuários". 
  - O teste confere se o JSON tem de fato as estruturas mapeadas (a chave `'sql'`).
  - O teste faz uma checagem elástica observando se a palavra `SELECT` e o alvo correto (`USUARIOS`) foram inferidos no campo de sql gerado dentro do dicionário.

## Executando os Testes

Para executar a suíte de testes, utilizamos o framework `pytest` a partir da raiz do projeto. Graças às configurações no arquivo `pytest.ini`, podemos separar a execução entre testes rápidos e lentos:

- **Rodar todos os testes:** `pytest -v`
- **Rodar apenas testes unitários (Rápidos):** `pytest -m "not integration" -v`
- **Rodar apenas testes de integração (Lentos, usa LLM):** `pytest -m "integration" -v`

## Debugando os Testes

Como não é trivial prever 100% da saída de um LLM, o debug costuma ser parte frequente da manutenção:
- **Usando `print()`:** Por padrão, o `pytest` "engole" saídas de print. Para visualizar no terminal (por exemplo, visualizar o DDL em texto puro sendo enviado à IA), adicione a flag `-s` na execução: `pytest -s`.
- **Modo Interativo (PDB):** Adicione a função nativa `breakpoint()` em qualquer lugar do arquivo de teste. A execução será congelada naquele ponto, permitindo que você inspecione as variáveis (`resultado`, `prompt`, etc) em tempo real pelo terminal.

### 3. Validações Manuais ("Scripts de Fumaça")

O projeto inclui pequenos scripts isolados — `teste_db.py` e `teste_ollama.py`. 
Eles não utilizam asserções do pytest. Servem como scripts *CLI* rápidos que rodam fora do Streamlit e são usados pelo desenvolvedor para testar sua infraestrutura local se algo falhar na subida do aplicativo web (ex: "As credenciais do `.env` e o banco Postgres local estão atrelados de fato?" ou "A rede do Ollama está rodando e consegue devolver um SQL simples no terminal?").