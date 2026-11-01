from core.query_plan import QueryPlan
from core.result_quality import build_interpretation, critique_result


def _plan():
    return QueryPlan.from_payload(
        {
            "intent": "Comparar receita por região",
            "tables": ["orders"],
            "relationships": [],
            "dimensions": ["region"],
            "metrics": ["revenue"],
            "filters": [],
            "grain": "region",
            "assumptions": ["revenue is represented by the order total"],
        }
    )


def test_zero_rows_receive_a_truthful_diagnostic_without_invented_values():
    result = {
        "columns": ["region", "revenue"],
        "rows": [],
        "row_count": 0,
        "truncated": False,
    }

    diagnostic = critique_result(result, _plan())

    assert diagnostic is not None
    assert diagnostic.kind == "empty_result"
    assert "não encontrou dados" in diagnostic.message
    assert diagnostic.expected_columns == ()


def test_missing_expected_columns_are_reported_without_rewriting_result():
    result = {
        "columns": ["region"],
        "rows": [{"region": "Sul"}],
        "row_count": 1,
        "truncated": False,
    }

    diagnostic = critique_result(result, _plan())

    assert diagnostic is not None
    assert diagnostic.kind == "missing_expected_columns"
    assert diagnostic.expected_columns == ("revenue",)


def test_interpretation_exposes_plan_and_temporal_assumptions():
    interpretation = build_interpretation(
        _plan(),
        {
            "label": "mês atual",
            "start": "2025-01-01",
            "end": "2025-02-01",
            "boundary": "start_inclusive_end_exclusive",
        },
    )

    assert interpretation == {
        "intent": "Comparar receita por região",
        "dimensions": ["region"],
        "metrics": ["revenue"],
        "period": {
            "label": "mês atual",
            "start": "2025-01-01",
            "end": "2025-02-01",
            "boundary": "start_inclusive_end_exclusive",
        },
        "assumptions": ["revenue is represented by the order total"],
    }
