import math
from datetime import date, datetime
from decimal import Decimal
from numbers import Real
from typing import Any, Dict, List, Mapping, TypedDict

import pandas as pd


class ResultPayload(TypedDict):
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    truncated: bool


def _decimal_values(rows: List[Dict[str, Any]], column: str) -> List[Decimal]:
    values = []
    for row in rows:
        value = row.get(column)
        if value is None or isinstance(value, bool):
            continue
        try:
            values.append(Decimal(str(value)))
        except (ArithmeticError, ValueError):
            continue
    return values


def _format_number(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return f"{normalized:.0f}"
    return f"{normalized:f}".rstrip("0").rstrip(".")


def _format_currency(value: Decimal) -> str:
    formatted = f"{value:,.2f}"
    return f"R$ {formatted.replace(',', 'X').replace('.', ',').replace('X', '.')}"


def summarize_result(result: ResultPayload) -> str:
    """Create a truthful summary from a bounded result payload."""

    columns = set(result["columns"])
    rows = result["rows"]
    row_count = result["row_count"]
    suffix = (
        " O resumo considera apenas as linhas retornadas porque o resultado "
        "foi limitado."
        if result["truncated"]
        else ""
    )

    if {"produto", "quantidade", "valor"}.issubset(columns):
        quantities = _decimal_values(rows, "quantidade")
        values = _decimal_values(rows, "valor")
        details = [f"Encontrei {len(rows)} produto(s)"]
        if quantities:
            details.append(
                f"totalizando {_format_number(sum(quantities))} unidade(s)"
            )
        if values:
            details.append(
                f"{_format_currency(sum(values))} em valor dos itens"
            )
        return ", ".join(details) + "." + suffix

    if "total_vendas" in columns:
        values = _decimal_values(rows, "total_vendas")
        if values:
            return f"O faturamento retornado foi {_format_currency(values[0])}.{suffix}"

    return f"A consulta retornou {row_count} linha(s).{suffix}"


def _is_null(value: Any) -> bool:
    if value is None:
        return True
    try:
        result = pd.isna(value)
    except (TypeError, ValueError):
        return False
    return isinstance(result, bool) and result


def _json_safe(value: Any) -> Any:
    if _is_null(value):
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Real):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        item = getattr(value, "item", None)
        return item() if callable(item) else value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def serialize_dataframe(
    dataframe: pd.DataFrame,
    max_rows: int = 5_000,
) -> ResultPayload:
    """Convert a DataFrame into a bounded, JSON-safe result payload."""

    if not isinstance(max_rows, int) or isinstance(max_rows, bool) or max_rows < 0:
        raise ValueError("max_rows must be a non-negative integer.")

    columns = [str(column) for column in dataframe.columns]
    row_count = len(dataframe)
    rows = [
        {
            column: _json_safe(value)
            for column, value in zip(columns, values)
        }
        for values in dataframe.head(max_rows).itertuples(
            index=False,
            name=None,
        )
    ]
    return {
        "columns": columns,
        "rows": rows,
        "row_count": row_count,
        "truncated": row_count > max_rows,
    }
