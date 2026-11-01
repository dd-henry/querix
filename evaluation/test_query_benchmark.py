import pytest

from evaluation.query_benchmark import (
    BenchmarkCase,
    BenchmarkResult,
    evaluate_benchmark,
)


def test_benchmark_reports_domain_neutral_quality_metrics():
    cases = [
        BenchmarkCase(
            name="revenue_by_region",
            question="Compare revenue by region",
            expected_columns=("region", "revenue"),
            min_row_count=1,
        ),
        BenchmarkCase(
            name="recent_orders",
            question="Show recent orders",
            expected_columns=("order_id", "created_at"),
            min_row_count=1,
        ),
        BenchmarkCase(
            name="invalid_request",
            question="Use an unavailable entity",
            expected_columns=("entity_id",),
        ),
    ]
    results = {
        "revenue_by_region": BenchmarkResult(
            executable=True,
            columns=("region", "revenue"),
            row_count=4,
            latency_ms=100,
        ),
        "recent_orders": BenchmarkResult(
            executable=True,
            columns=("order_id",),
            row_count=0,
            latency_ms=200,
        ),
        "invalid_request": BenchmarkResult(
            executable=False,
            latency_ms=50,
        ),
    }

    report = evaluate_benchmark(cases, results)

    assert report.total_cases == 3
    assert report.executable_cases == 2
    assert report.executable_rate == pytest.approx(2 / 3)
    assert report.expected_column_coverage == pytest.approx(3 / 5)
    assert report.zero_row_rate == pytest.approx(1 / 2)
    assert report.average_latency_ms == pytest.approx(350 / 3)
    assert report.row_constraint_pass_rate == pytest.approx(1 / 2)


def test_benchmark_accepts_recorded_case_and_result_mappings():
    case = BenchmarkCase.from_mapping(
        {
            "name": "case-1",
            "question": "List accounts",
            "expected_columns": ["account_id"],
            "max_row_count": 10,
        }
    )
    result = BenchmarkResult.from_mapping(
        {
            "executable": True,
            "columns": ["ACCOUNT_ID"],
            "row_count": 2,
            "latency_ms": 12.5,
        }
    )

    report = evaluate_benchmark([case], {"case-1": result})

    assert report.to_dict() == {
        "total_cases": 1,
        "executable_cases": 1,
        "executable_rate": 1.0,
        "expected_column_coverage": 1.0,
        "zero_row_rate": 0.0,
        "average_latency_ms": 12.5,
        "row_constraint_pass_rate": 1.0,
    }


def test_benchmark_rejects_missing_or_unexpected_results():
    cases = [BenchmarkCase(name="case-1", question="List accounts")]

    with pytest.raises(ValueError, match="missing results"):
        evaluate_benchmark(cases, {})

    with pytest.raises(ValueError, match="unexpected results"):
        evaluate_benchmark(
            cases,
            {
                "case-1": BenchmarkResult(executable=False),
                "case-2": BenchmarkResult(executable=False),
            },
        )
