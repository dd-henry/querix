import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from typing import Dict, Optional, Tuple


_MONTHS = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}


@dataclass(frozen=True)
class SupportingQuery:
    key: str
    title: str
    sql: str
    parameters: Dict[str, str]

    def as_translation(self) -> dict:
        return {
            "key": self.key,
            "title": self.title,
            "sql": self.sql,
            "parameters": self.parameters,
        }


@dataclass(frozen=True)
class AnalyticalQuery:
    sql: str
    parameters: Dict[str, str]
    intent: str
    supporting_queries: Tuple[SupportingQuery, ...] = field(
        default_factory=tuple
    )

    def as_translation(self) -> dict:
        return {
            "sql": self.sql,
            "grafico": None,
            "parameters": self.parameters,
            "intent": self.intent,
            "supporting_queries": [
                query.as_translation()
                for query in self.supporting_queries
            ],
        }


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    return "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )


def _period(question: str, reference_date: date) -> Optional[Tuple[str, str]]:
    normalized = _normalize(question)
    year_match = re.search(r"\b(20\d{2})\b", normalized)
    year = int(year_match.group(1)) if year_match else reference_date.year

    month_number: Optional[int] = None
    for month_name, number in _MONTHS.items():
        if re.search(rf"\b{month_name}\b", normalized):
            month_number = number
            break

    if month_number is None:
        number_match = re.search(
            r"\b(?:mes|month)\s+(?:de\s+)?(\d{1,2})\b",
            normalized,
        )
        if number_match:
            month_number = int(number_match.group(1))

    if month_number is not None and not 1 <= month_number <= 12:
        return None

    if month_number is None:
        explicit_month_match = re.search(
            r"\b(?:mes|month)\s+(?:de\s+)?([a-z]+|\d{1,2})\b",
            normalized,
        )
        if explicit_month_match:
            relative_months = {"atual", "corrente", "current", "this"}
            if explicit_month_match.group(1) not in relative_months:
                return None
        month_number = reference_date.month

    start = date(year, month_number, 1)
    if month_number == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month_number + 1, 1)

    def iso_start(value: date) -> str:
        return datetime.combine(
            value,
            time.min,
            tzinfo=timezone.utc,
        ).isoformat()

    return iso_start(start), iso_start(end)


def _parameters(question: str, reference_date: Optional[date]) -> Optional[Dict[str, str]]:
    period = _period(question, reference_date or date.today())
    if period is None:
        return None
    start, end = period
    return {
        "period_start": start,
        "period_end": end,
    }


def _is_product_question(question: str) -> bool:
    normalized = _normalize(question)
    return any(
        phrase in normalized
        for phrase in (
            "produto",
            "produtos",
            "item vendido",
            "itens vendidos",
            "vendas por produto",
        )
    )


def _is_revenue_question(question: str) -> bool:
    normalized = _normalize(question)
    return any(
        phrase in normalized
        for phrase in (
            "faturamento",
            "receita",
            "total de vendas",
            "total vendido",
            "valor total das vendas",
        )
    ) and not _is_product_question(question)


def _is_sales_list_question(question: str) -> bool:
    normalized = _normalize(question)
    return any(
        phrase in normalized
        for phrase in (
            "quais foram as vendas",
            "quais sao as vendas",
            "listar vendas",
            "liste as vendas",
            "vendas realizadas",
            "vendas do periodo",
            "vendas deste mes",
            "vendas desse mes",
        )
    )


def _supporting_sales_queries(
    parameters: Dict[str, str],
) -> Tuple[SupportingQuery, ...]:
    return (
        SupportingQuery(
            key="sales_kpis",
            title="Indicadores do período",
            sql=(
                "SELECT COUNT(*) AS quantidade_vendas, "
                "COALESCE(SUM(v.valor_total), 0) AS faturamento, "
                "COALESCE(AVG(v.valor_total), 0) AS ticket_medio "
                "FROM vendas v "
                "WHERE v.status = 'concluida' "
                "AND v.data_hora >= :period_start "
                "AND v.data_hora < :period_end"
            ),
            parameters=parameters,
        ),
        SupportingQuery(
            key="top_products",
            title="Produtos mais vendidos",
            sql=(
                "SELECT p.nome AS produto, "
                "SUM(iv.quantidade) AS quantidade, "
                "SUM(iv.subtotal) AS valor "
                "FROM vendas v "
                "JOIN itens_venda iv ON iv.venda_id = v.id "
                "JOIN produtos p ON p.id = iv.produto_id "
                "WHERE v.status = 'concluida' "
                "AND v.data_hora >= :period_start "
                "AND v.data_hora < :period_end "
                "GROUP BY p.id, p.nome "
                "ORDER BY quantidade DESC, valor DESC, produto "
                "LIMIT 5"
            ),
            parameters=parameters,
        ),
        SupportingQuery(
            key="payment_methods",
            title="Vendas por forma de pagamento",
            sql=(
                "SELECT v.forma_pagamento, "
                "COUNT(*) AS quantidade_vendas, "
                "COALESCE(SUM(v.valor_total), 0) AS faturamento "
                "FROM vendas v "
                "WHERE v.status = 'concluida' "
                "AND v.data_hora >= :period_start "
                "AND v.data_hora < :period_end "
                "GROUP BY v.forma_pagamento "
                "ORDER BY faturamento DESC, v.forma_pagamento"
            ),
            parameters=parameters,
        ),
    )


def build_known_query(
    question: str,
    reference_date: Optional[date] = None,
) -> Optional[AnalyticalQuery]:
    if not isinstance(question, str) or not question.strip():
        return None

    parameters = _parameters(question, reference_date)
    if parameters is None:
        return None

    if _is_product_question(question):
        return AnalyticalQuery(
            sql=(
                "SELECT p.nome AS produto, "
                "SUM(iv.quantidade) AS quantidade, "
                "SUM(iv.subtotal) AS valor "
                "FROM vendas v "
                "JOIN itens_venda iv ON iv.venda_id = v.id "
                "JOIN produtos p ON p.id = iv.produto_id "
                "WHERE v.status = 'concluida' "
                "AND v.data_hora >= :period_start "
                "AND v.data_hora < :period_end "
                "GROUP BY p.id, p.nome "
                "ORDER BY valor DESC, produto"
            ),
            parameters=parameters,
            intent="product_sales",
            supporting_queries=_supporting_sales_queries(parameters),
        )

    if _is_revenue_question(question):
        return AnalyticalQuery(
            sql=(
                "SELECT COALESCE(SUM(v.valor_total), 0) AS total_vendas "
                "FROM vendas v "
                "WHERE v.status = 'concluida' "
                "AND v.data_hora >= :period_start "
                "AND v.data_hora < :period_end"
            ),
            parameters=parameters,
            intent="revenue_total",
            supporting_queries=_supporting_sales_queries(parameters),
        )

    if _is_sales_list_question(question):
        return AnalyticalQuery(
            sql=(
                "SELECT v.id, v.cliente_id, v.funcionario_id, "
                "v.data_hora, v.status, v.forma_pagamento, "
                "v.valor_total, v.desconto "
                "FROM vendas v "
                "WHERE v.status = 'concluida' "
                "AND v.data_hora >= :period_start "
                "AND v.data_hora < :period_end "
                "ORDER BY v.data_hora, v.id"
            ),
            parameters=parameters,
            intent="sales_list",
            supporting_queries=_supporting_sales_queries(parameters),
        )

    return None
