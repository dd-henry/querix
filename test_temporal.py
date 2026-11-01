from datetime import date

from core.temporal import TemporalInterpreter


def test_month_without_year_uses_reference_year():
    interpretation = TemporalInterpreter().interpret(
        "Quero os registros de março",
        reference_date=date(2025, 10, 15),
    )

    assert interpretation.start == date(2025, 3, 1)
    assert interpretation.end == date(2025, 4, 1)
    assert interpretation.label == "março de 2025"


def test_explicit_year_overrides_reference_year_and_accepts_accent_variant():
    interpretation = TemporalInterpreter().interpret(
        "Compare os dados de marco de 2023",
        reference_date=date(2025, 10, 15),
    )

    assert interpretation.start == date(2023, 3, 1)
    assert interpretation.end == date(2023, 4, 1)
    assert interpretation.label == "março de 2023"


def test_current_and_previous_month_use_half_open_boundaries():
    interpreter = TemporalInterpreter()

    current = interpreter.interpret(
        "Mostre o mês atual",
        reference_date=date(2025, 1, 15),
    )
    previous = interpreter.interpret(
        "Mostre o último mês",
        reference_date=date(2025, 1, 15),
    )

    assert (current.start, current.end) == (
        date(2025, 1, 1),
        date(2025, 2, 1),
    )
    assert (previous.start, previous.end) == (
        date(2024, 12, 1),
        date(2025, 1, 1),
    )


def test_current_year_uses_start_of_next_year_as_exclusive_end():
    interpretation = TemporalInterpreter().interpret(
        "Total do ano atual",
        reference_date=date(2025, 10, 15),
    )

    assert (interpretation.start, interpretation.end) == (
        date(2025, 1, 1),
        date(2026, 1, 1),
    )


def test_relative_day_window_crosses_year_boundary():
    interpretation = TemporalInterpreter().interpret(
        "Eventos dos últimos 7 dias",
        reference_date=date(2025, 1, 3),
    )

    assert (interpretation.start, interpretation.end) == (
        date(2024, 12, 28),
        date(2025, 1, 4),
    )


def test_question_without_temporal_expression_has_no_filter():
    interpretation = TemporalInterpreter().interpret(
        "Quais são as categorias disponíveis?",
        reference_date=date(2025, 10, 15),
    )

    assert interpretation.start is None
    assert interpretation.end is None
    assert interpretation.label is None
    assert interpretation.has_filter is False
