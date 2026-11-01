import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional


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
_MONTH_LABELS = {
    1: "janeiro",
    2: "fevereiro",
    3: "março",
    4: "abril",
    5: "maio",
    6: "junho",
    7: "julho",
    8: "agosto",
    9: "setembro",
    10: "outubro",
    11: "novembro",
    12: "dezembro",
}
_MONTH_PATTERN = "|".join(_MONTHS)
_MONTH_WITH_YEAR = re.compile(
    rf"\b(?P<month>{_MONTH_PATTERN})(?:\s+(?:de\s+)?|/|-)"
    rf"(?P<year>\d{{4}})\b"
)
_MONTH_ONLY = re.compile(rf"\b(?P<month>{_MONTH_PATTERN})\b")
_RELATIVE_DAYS = re.compile(r"\b(?:ultimos?|ultimas?)\s+(\d+)\s+dias?\b")


@dataclass(frozen=True)
class TemporalInterpretation:
    start: Optional[date] = None
    end: Optional[date] = None
    label: Optional[str] = None
    matched_expression: Optional[str] = None

    @property
    def has_filter(self) -> bool:
        return self.start is not None and self.end is not None

    @property
    def planning_hint(self) -> Optional[dict[str, str]]:
        if not self.has_filter:
            return None
        return {
            "label": self.label or "",
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "boundary": "start_inclusive_end_exclusive",
        }


class TemporalInterpreter:
    """Resolve supported Portuguese temporal expressions into date intervals."""

    def interpret(
        self,
        question: str,
        reference_date: date,
    ) -> TemporalInterpretation:
        normalized_question = _normalize(question)

        relative = _RELATIVE_DAYS.search(normalized_question)
        if relative:
            days = int(relative.group(1))
            if days > 0:
                return TemporalInterpretation(
                    start=reference_date - timedelta(days=days - 1),
                    end=reference_date + timedelta(days=1),
                    label=f"últimos {days} dias",
                    matched_expression=relative.group(0),
                )

        if _contains_any(
            normalized_question,
            ("hoje",),
        ):
            return _daily_interval(reference_date, "hoje")

        if _contains_any(normalized_question, ("ontem",)):
            return _daily_interval(
                reference_date - timedelta(days=1),
                "ontem",
            )

        if _contains_any(
            normalized_question,
            ("mes atual", "mes corrente", "este mes", "neste mes"),
        ):
            return _month_interval(
                reference_date.year,
                reference_date.month,
                "mês atual",
            )

        if _contains_any(
            normalized_question,
            ("mes passado", "mes anterior", "ultimo mes"),
        ):
            previous_month = _shift_month(reference_date.year, reference_date.month, -1)
            return _month_interval(
                previous_month[0],
                previous_month[1],
                "mês anterior",
            )

        if _contains_any(
            normalized_question,
            ("ano atual", "ano corrente", "este ano", "neste ano"),
        ):
            return TemporalInterpretation(
                start=date(reference_date.year, 1, 1),
                end=date(reference_date.year + 1, 1, 1),
                label=f"ano de {reference_date.year}",
                matched_expression="ano atual",
            )

        month_with_year = _MONTH_WITH_YEAR.search(normalized_question)
        if month_with_year:
            month_name = month_with_year.group("month")
            year = int(month_with_year.group("year"))
            return _month_interval(
                year,
                _MONTHS[month_name],
                f"{_MONTH_LABELS[_MONTHS[month_name]]} de {year}",
                month_with_year.group(0),
            )

        month_only = _MONTH_ONLY.search(normalized_question)
        if month_only:
            month_name = month_only.group("month")
            month = _MONTHS[month_name]
            return _month_interval(
                reference_date.year,
                month,
                f"{_MONTH_LABELS[month]} de {reference_date.year}",
                month_only.group(0),
            )

        return TemporalInterpretation()


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.lower())
    without_accents = "".join(
        character
        for character in decomposed
        if unicodedata.category(character) != "Mn"
    )
    return " ".join(without_accents.split())


def _contains_any(value: str, phrases: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(phrase)}\b", value) for phrase in phrases)


def _month_interval(
    year: int,
    month: int,
    label: str,
    matched_expression: Optional[str] = None,
) -> TemporalInterpretation:
    next_year, next_month = _shift_month(year, month, 1)
    return TemporalInterpretation(
        start=date(year, month, 1),
        end=date(next_year, next_month, 1),
        label=label,
        matched_expression=matched_expression,
    )


def _daily_interval(day: date, label: str) -> TemporalInterpretation:
    return TemporalInterpretation(
        start=day,
        end=day + timedelta(days=1),
        label=label,
        matched_expression=label,
    )


def _shift_month(year: int, month: int, offset: int) -> tuple[int, int]:
    zero_based = year * 12 + month - 1 + offset
    return zero_based // 12, zero_based % 12 + 1
