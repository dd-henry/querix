from datetime import date

from core.analytical_queries import build_known_query


def test_builds_august_revenue_query_for_completed_sales():
    result = build_known_query(
        "Qual foi o total de vendas do mês de agosto de 2026?",
        reference_date=date(2026, 10, 31),
    )

    assert result is not None
    assert result.intent == "revenue_total"
    assert result.parameters == {
        "period_start": "2026-08-01T00:00:00+00:00",
        "period_end": "2026-09-01T00:00:00+00:00",
    }
    assert "COALESCE(SUM(v.valor_total), 0)" in result.sql
    assert "v.status = 'concluida'" in result.sql
    assert "v.data_hora >= :period_start" in result.sql
    assert "v.data_hora < :period_end" in result.sql


def test_builds_grouped_product_query_with_quantity_and_value():
    result = build_known_query(
        "Quais foram os produtos vendidos em agosto?",
        reference_date=date(2026, 10, 31),
    )

    assert result is not None
    assert result.intent == "product_sales"
    assert "p.nome AS produto" in result.sql
    assert "SUM(iv.quantidade) AS quantidade" in result.sql
    assert "SUM(iv.subtotal) AS valor" in result.sql
    assert "JOIN itens_venda iv" in result.sql
    assert "JOIN produtos p" in result.sql
    assert "GROUP BY p.id, p.nome" in result.sql
    assert "v.status = 'concluida'" in result.sql
    assert result.parameters["period_start"] == "2026-08-01T00:00:00+00:00"
    assert result.parameters["period_end"] == "2026-09-01T00:00:00+00:00"


def test_uses_reference_month_when_period_is_omitted():
    result = build_known_query(
        "Qual o faturamento deste mês?",
        reference_date=date(2026, 10, 31),
    )

    assert result is not None
    assert result.parameters == {
        "period_start": "2026-10-01T00:00:00+00:00",
        "period_end": "2026-11-01T00:00:00+00:00",
    }


def test_unknown_intent_falls_back_to_llm():
    assert build_known_query("Quais fornecedores estão ativos?") is None


def test_invalid_numeric_month_does_not_fabricate_a_period():
    assert (
        build_known_query(
            "Qual foi o total de vendas do mês 13?",
            reference_date=date(2026, 10, 31),
        )
        is None
    )


def test_unknown_text_month_falls_back_to_llm():
    assert (
        build_known_query(
            "Qual foi o total de vendas do mês de smarch?",
            reference_date=date(2026, 10, 31),
        )
        is None
    )
