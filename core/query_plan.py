from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Optional


class QueryPlanError(ValueError):
    """Raised when the model does not return a valid analytical plan."""


@dataclass(frozen=True)
class QueryPlan:
    intent: str
    tables: tuple[str, ...]
    relationships: tuple[str, ...]
    dimensions: tuple[str, ...]
    metrics: tuple[str, ...]
    filters: tuple[dict[str, object], ...]
    grain: Optional[str]
    assumptions: tuple[str, ...]

    @classmethod
    def from_payload(cls, payload: object) -> "QueryPlan":
        if not isinstance(payload, Mapping):
            raise QueryPlanError("The planner response must be a JSON object.")

        intent = _required_text(payload, "intent")
        tables = _text_sequence(payload, "tables", required=True)
        relationships = _text_sequence(
            payload,
            "relationships",
            allow_empty_items=True,
        )
        dimensions = _text_sequence(
            payload,
            "dimensions",
            allow_empty_items=True,
        )
        metrics = _text_sequence(
            payload,
            "metrics",
            allow_empty_items=True,
        )
        assumptions = _text_sequence(
            payload,
            "assumptions",
            required=True,
            allow_single_text=True,
        )
        filters = _filters(payload.get("filters"))
        grain = payload.get("grain")
        if grain is not None and (
            not isinstance(grain, str) or not grain.strip()
        ):
            raise QueryPlanError("The planner field 'grain' must be a string or null.")

        return cls(
            intent=intent,
            tables=tables,
            relationships=relationships,
            dimensions=dimensions,
            metrics=metrics,
            filters=filters,
            grain=grain.strip() if isinstance(grain, str) else None,
            assumptions=assumptions,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "intent": self.intent,
            "tables": list(self.tables),
            "relationships": list(self.relationships),
            "dimensions": list(self.dimensions),
            "metrics": list(self.metrics),
            "filters": [dict(item) for item in self.filters],
            "grain": self.grain,
            "assumptions": list(self.assumptions),
        }


def _required_text(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise QueryPlanError(f"The planner field '{field}' must be a non-empty string.")
    return value.strip()


def _text_sequence(
    payload: Mapping[str, object],
    field: str,
    required: bool = False,
    allow_empty_items: bool = False,
    allow_single_text: bool = False,
) -> tuple[str, ...]:
    value = payload.get(field)
    if isinstance(value, str) and allow_single_text:
        value = [value]
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise QueryPlanError(f"The planner field '{field}' must be an array.")

    normalized = []
    for item in value:
        if not isinstance(item, str):
            raise QueryPlanError(
                f"The planner field '{field}' must contain non-empty strings."
            )
        normalized_item = item.strip()
        if not normalized_item:
            if allow_empty_items:
                continue
            raise QueryPlanError(
                f"The planner field '{field}' must contain non-empty strings."
            )
        normalized.append(normalized_item)
    if required and not normalized:
        raise QueryPlanError(f"The planner field '{field}' must not be empty.")
    return tuple(normalized)


def _filters(value: object) -> tuple[dict[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise QueryPlanError("The planner field 'filters' must be an array.")
    normalized = []
    for item in value:
        if not isinstance(item, Mapping):
            raise QueryPlanError("The planner field 'filters' must contain objects.")
        normalized.append(dict(item))
    return tuple(normalized)
