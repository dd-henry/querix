from dataclasses import dataclass
from typing import Any, Mapping, Optional

from api.serializers.results import ResultPayload
from core.query_plan import QueryPlan


@dataclass(frozen=True)
class ResultDiagnostics:
    kind: str
    message: str
    expected_columns: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "message": self.message,
            "expected_columns": list(self.expected_columns),
        }


def build_interpretation(
    plan: object,
    temporal: object = None,
) -> Optional[dict[str, object]]:
    values = _plan_values(plan)
    if values is None:
        return None

    period = dict(temporal) if isinstance(temporal, Mapping) else None
    return {
        "intent": values["intent"],
        "dimensions": list(values["dimensions"]),
        "metrics": list(values["metrics"]),
        "period": period,
        "assumptions": list(values["assumptions"]),
    }


def critique_result(
    result: ResultPayload,
    plan: object,
) -> Optional[ResultDiagnostics]:
    values = _plan_values(plan)
    if values is None:
        return None

    if result["row_count"] == 0:
        return ResultDiagnostics(
            kind="empty_result",
            message=(
                "A consulta foi executada, mas não encontrou dados "
                "compatíveis com os filtros informados."
            ),
        )

    return None


def _plan_values(plan: object) -> Optional[dict[str, Any]]:
    if isinstance(plan, QueryPlan):
        return plan.to_dict()
    if not isinstance(plan, Mapping):
        return None

    fields = ("intent", "dimensions", "metrics", "assumptions")
    if any(field not in plan for field in fields):
        return None
    return {
        "intent": _text(plan["intent"]),
        "dimensions": _texts(plan["dimensions"]),
        "metrics": _texts(plan["metrics"]),
        "assumptions": _texts(plan["assumptions"]),
    }


def _text(value: object) -> str:
    return str(value).strip()


def _texts(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [_text(item) for item in value if _text(item)]
