from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence


@dataclass(frozen=True)
class BenchmarkCase:
    """A natural-language case and the observable quality it should satisfy."""

    name: str
    question: str
    expected_columns: tuple[str, ...] = ()
    min_row_count: Optional[int] = None
    max_row_count: Optional[int] = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Benchmark case name must not be empty.")
        if not self.question.strip():
            raise ValueError("Benchmark case question must not be empty.")
        if any(not column.strip() for column in self.expected_columns):
            raise ValueError("Expected column names must not be empty.")
        if self.min_row_count is not None and self.min_row_count < 0:
            raise ValueError("min_row_count must not be negative.")
        if self.max_row_count is not None and self.max_row_count < 0:
            raise ValueError("max_row_count must not be negative.")
        if (
            self.min_row_count is not None
            and self.max_row_count is not None
            and self.min_row_count > self.max_row_count
        ):
            raise ValueError("min_row_count must not exceed max_row_count.")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "BenchmarkCase":
        return cls(
            name=str(value.get("name", "")),
            question=str(value.get("question", "")),
            expected_columns=tuple(
                str(column) for column in value.get("expected_columns", ())
            ),
            min_row_count=_optional_int(value.get("min_row_count")),
            max_row_count=_optional_int(value.get("max_row_count")),
        )


@dataclass(frozen=True)
class BenchmarkResult:
    """Recorded output for a case; no database or model call is made here."""

    executable: bool
    columns: tuple[str, ...] = ()
    row_count: int = 0
    latency_ms: float = 0.0

    def __post_init__(self) -> None:
        if self.row_count < 0:
            raise ValueError("row_count must not be negative.")
        if self.latency_ms < 0:
            raise ValueError("latency_ms must not be negative.")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "BenchmarkResult":
        return cls(
            executable=bool(value.get("executable", False)),
            columns=tuple(str(column) for column in value.get("columns", ())),
            row_count=int(value.get("row_count", 0)),
            latency_ms=float(value.get("latency_ms", 0.0)),
        )


@dataclass(frozen=True)
class BenchmarkReport:
    total_cases: int
    executable_cases: int
    executable_rate: float
    expected_column_coverage: float
    zero_row_rate: float
    average_latency_ms: float
    row_constraint_pass_rate: Optional[float]

    def to_dict(self) -> dict[str, object]:
        return {
            "total_cases": self.total_cases,
            "executable_cases": self.executable_cases,
            "executable_rate": self.executable_rate,
            "expected_column_coverage": self.expected_column_coverage,
            "zero_row_rate": self.zero_row_rate,
            "average_latency_ms": self.average_latency_ms,
            "row_constraint_pass_rate": self.row_constraint_pass_rate,
        }


def evaluate_benchmark(
    cases: Sequence[BenchmarkCase],
    results: Mapping[str, BenchmarkResult],
) -> BenchmarkReport:
    """Aggregate observable quality metrics from recorded case results."""

    case_names = [case.name for case in cases]
    if len(set(case_names)) != len(case_names):
        raise ValueError("Benchmark case names must be unique.")

    missing = [name for name in case_names if name not in results]
    unexpected = [name for name in results if name not in case_names]
    if missing or unexpected:
        details = []
        if missing:
            details.append(f"missing results: {', '.join(missing)}")
        if unexpected:
            details.append(f"unexpected results: {', '.join(unexpected)}")
        raise ValueError("Benchmark results do not match cases (" + "; ".join(details) + ").")

    total_cases = len(cases)
    recorded = [results[case.name] for case in cases]
    executable_cases = sum(result.executable for result in recorded)
    total_expected = sum(len(case.expected_columns) for case in cases)
    matched_expected = sum(
        _matched_columns(case.expected_columns, results[case.name].columns)
        for case in cases
    )
    zero_row_count = sum(
        result.executable and result.row_count == 0 for result in recorded
    )
    constrained_cases = [
        (case, results[case.name])
        for case in cases
        if case.min_row_count is not None or case.max_row_count is not None
    ]
    passed_constraints = sum(
        _row_constraints_pass(case, result)
        for case, result in constrained_cases
    )

    return BenchmarkReport(
        total_cases=total_cases,
        executable_cases=executable_cases,
        executable_rate=_ratio(executable_cases, total_cases),
        expected_column_coverage=(
            _ratio(matched_expected, total_expected)
            if total_expected
            else 1.0
        ),
        zero_row_rate=_ratio(zero_row_count, executable_cases),
        average_latency_ms=(
            sum(result.latency_ms for result in recorded) / total_cases
            if total_cases
            else 0.0
        ),
        row_constraint_pass_rate=(
            _ratio(passed_constraints, len(constrained_cases))
            if constrained_cases
            else None
        ),
    )


def _matched_columns(
    expected_columns: Sequence[str],
    actual_columns: Sequence[str],
) -> int:
    actual = {column.casefold() for column in actual_columns}
    return sum(column.casefold() in actual for column in expected_columns)


def _row_constraints_pass(
    case: BenchmarkCase,
    result: BenchmarkResult,
) -> bool:
    if not result.executable:
        return False
    if case.min_row_count is not None and result.row_count < case.min_row_count:
        return False
    if case.max_row_count is not None and result.row_count > case.max_row_count:
        return False
    return True


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _optional_int(value: object) -> Optional[int]:
    return None if value is None else int(value)
