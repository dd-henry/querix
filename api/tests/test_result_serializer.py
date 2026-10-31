import json
from datetime import date, datetime, timezone
from decimal import Decimal

import pandas as pd

from api.serializers.results import serialize_dataframe


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
