# Avaliação de consultas analíticas

O benchmark em [`evaluation/query_benchmark.py`](../evaluation/query_benchmark.py)
mede a qualidade observável do pipeline sem executar banco de dados ou Ollama.
Ele recebe perguntas, expectativas de colunas e restrições opcionais de
quantidade de linhas, além dos resultados registrados de cada caso.

## Contrato

Cada `BenchmarkCase` contém:

- `name`: identificador único;
- `question`: pergunta usada no teste;
- `expected_columns`: colunas que o resultado deveria conter;
- `min_row_count` e `max_row_count`: limites opcionais.

Cada `BenchmarkResult` contém somente evidências observáveis:

- `executable`: se a consulta chegou a ser executável;
- `columns` e `row_count`: estrutura do resultado;
- `latency_ms`: latência registrada pelo chamador.

Não há SQL, nomes de tabelas ou regras de negócio no contrato do benchmark.
Para um novo nicho, adicione casos com as perguntas e colunas esperadas do
schema avaliado, sem alterar o código do benchmark.

## Métricas

`evaluate_benchmark` retorna:

- `executable_rate`: casos executáveis dividido pelo total;
- `expected_column_coverage`: colunas esperadas encontradas dividido pelo
  total de colunas esperadas, comparando sem diferenciar maiúsculas;
- `zero_row_rate`: casos executáveis sem linhas dividido pelos casos
  executáveis;
- `average_latency_ms`: média da latência registrada por caso;
- `row_constraint_pass_rate`: taxa de atendimento das restrições de linhas
  entre os casos que definiram uma restrição.

Uma lista sem colunas esperadas recebe cobertura `1.0`, pois não há lacuna
observável para medir. Uma lista sem casos tem taxa executável, taxa de
linhas vazias e latência iguais a `0.0`.

## Exemplo

```python
from evaluation.query_benchmark import (
    BenchmarkCase,
    BenchmarkResult,
    evaluate_benchmark,
)

cases = [
    BenchmarkCase(
        name="accounts_by_region",
        question="Compare accounts by region",
        expected_columns=("region", "account_count"),
        min_row_count=1,
    )
]
results = {
    "accounts_by_region": BenchmarkResult(
        executable=True,
        columns=("region", "account_count"),
        row_count=3,
        latency_ms=184.2,
    )
}

report = evaluate_benchmark(cases, results)
print(report.to_dict())
```

Os testes do contrato são executados junto com a suíte unitária:

```bash
./venv/bin/pytest evaluation/test_query_benchmark.py -q
```
