import json
from datetime import date, datetime, timezone
from decimal import Decimal

import pandas as pd

from api.serializers.results import serialize_dataframe, summarize_result


def test_serialize_empty_dataframe_preserves_columns_and_shape():
    result = serialize_dataframe(pd.DataFrame(columns=["id", "name"]))

    assert result == {
        "columns": ["id", "name"],
        "rows": [],
        "row_count": 0,
        "truncated": False,
    }


def test_serialize_dataframe_returns_all_bounded_rows():
    dataframe = pd.DataFrame(
        [
            {"id": 1, "name": "Ada"},
            {"id": 2, "name": "Grace"},
        ]
    )

    result = serialize_dataframe(dataframe, max_rows=2)

    assert result["rows"] == [
        {"id": 1, "name": "Ada"},
        {"id": 2, "name": "Grace"},
    ]
    assert result["row_count"] == 2
    assert result["truncated"] is False


def test_serialize_dataframe_limits_rows_and_marks_truncation():
    dataframe = pd.DataFrame(
        [
            {"id": 1},
            {"id": 2},
            {"id": 3},
        ]
    )

    result = serialize_dataframe(dataframe, max_rows=2)

    assert result["rows"] == [{"id": 1}, {"id": 2}]
    assert result["row_count"] == 3
    assert result["truncated"] is True


def test_serialize_dataframe_normalizes_special_values_deterministically():
    dataframe = pd.DataFrame(
        [
            {
                "null": None,
                "nan": float("nan"),
                "date": date(2025, 1, 2),
                "datetime": datetime(
                    2025,
                    1,
                    2,
                    12,
                    30,
                    tzinfo=timezone.utc,
                ),
                "decimal": Decimal("12.3400"),
            }
        ]
    )

    result = serialize_dataframe(dataframe)

    assert result["rows"] == [
        {
            "null": None,
            "nan": None,
            "date": "2025-01-02",
            "datetime": "2025-01-02T12:30:00+00:00",
            "decimal": "12.3400",
        }
    ]
    assert json.dumps(result, sort_keys=True) == (
        '{"columns": ["null", "nan", "date", "datetime", "decimal"], '
        '"row_count": 1, "rows": [{"date": "2025-01-02", '
        '"datetime": "2025-01-02T12:30:00+00:00", "decimal": "12.3400", '
        '"nan": null, "null": null}], "truncated": false}'
    )


def test_summarize_product_result_includes_rows_quantity_and_value():
    result = {
        "columns": ["produto", "quantidade", "valor"],
        "rows": [
            {"produto": "Picanha", "quantidade": "2", "valor": "10.00"},
            {"produto": "Cerveja", "quantidade": "3", "valor": "5.50"},
        ],
        "row_count": 2,
        "truncated": False,
    }

    assert summarize_result(result) == (
        "Encontrei 2 produto(s), totalizando 5 unidade(s), "
        "R$ 15,50 em valor dos itens."
    )


def test_summarize_revenue_result_uses_returned_total():
    result = {
        "columns": ["total_vendas"],
        "rows": [{"total_vendas": "1498.00"}],
        "row_count": 1,
        "truncated": False,
    }

    assert summarize_result(result) == "O faturamento retornado foi R$ 1.498,00."


def test_summarize_result_ignores_invalid_metrics_and_marks_truncation():
    result = {
        "columns": ["produto", "quantidade", "valor"],
        "rows": [
            {"produto": "Picanha", "quantidade": None, "valor": "invalido"},
        ],
        "row_count": 5001,
        "truncated": True,
    }

    assert summarize_result(result) == (
        "Encontrei 1 produto(s). O resumo considera apenas as linhas "
        "retornadas porque o resultado foi limitado."
    )
