import re
from collections.abc import Mapping
from typing import Iterable, Optional

from core.query_plan import QueryPlan
from core.semantic_context import SemanticProfile
from database.predefined_queries import PredefinedQueryRepository


class QueryValidationError(ValueError):
    """Stable validation failure for a plan or generated SQL."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class PlanValidator:
    @staticmethod
    def validate_plan(plan: QueryPlan, profile: SemanticProfile) -> None:
        for table_name in plan.tables:
            if table_name not in profile.tables:
                raise QueryValidationError(
                    "unknown_table",
                    f"Unknown table in query plan: {table_name}.",
                )

        known_relationships = {
            _relationship_key(
                relationship.table,
                relationship.column,
                relationship.foreign_table,
                relationship.foreign_column,
            )
            for relationship in profile.relationships
        }
        for relationship in plan.relationships:
            normalized = _normalize_relationship(relationship)
            if normalized not in known_relationships:
                raise QueryValidationError(
                    "unknown_relationship",
                    f"Unknown relationship in query plan: {relationship}.",
                )

        expressions: Iterable[str] = (
            *plan.dimensions,
            *plan.metrics,
        )
        for expression in expressions:
            _validate_expression(expression, plan, profile)

        for item in plan.filters:
            column = item.get("column")
            if not isinstance(column, str) or not column.strip():
                raise QueryValidationError(
                    "invalid_filter",
                    "Every query-plan filter must identify a column.",
                )
            _validate_expression(column, plan, profile)

    @staticmethod
    def validate_sql(sql: str) -> str:
        try:
            return PredefinedQueryRepository.validate_query(sql, [])
        except (AttributeError, TypeError, ValueError) as exc:
            raise QueryValidationError(
                "sql_not_read_only",
                "Generated SQL must be a single read-only SELECT or WITH statement.",
            ) from exc


_QUALIFIED_IDENTIFIER = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\b"
)
_IDENTIFIER = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
_OUTPUT_ALIAS = re.compile(
    r"\bas\s+[A-Za-z_][A-Za-z0-9_]*\s*$",
    re.IGNORECASE,
)
_IGNORED_WORDS = {
    "and",
    "as",
    "asc",
    "avg",
    "by",
    "case",
    "cast",
    "coalesce",
    "count",
    "date",
    "day",
    "desc",
    "distinct",
    "else",
    "end",
    "extract",
    "false",
    "from",
    "hour",
    "max",
    "min",
    "month",
    "null",
    "on",
    "or",
    "over",
    "partition",
    "sum",
    "then",
    "true",
    "when",
    "where",
    "year",
}


def _validate_expression(
    expression: str,
    plan: QueryPlan,
    profile: SemanticProfile,
) -> None:
    references = tuple(_column_references(expression))
    for table_name, column_name in references:
        if table_name is not None:
            _validate_qualified_column(table_name, column_name, profile)
            continue

        matches = [
            table
            for table in plan.tables
            if any(column.name == column_name for column in profile.tables[table].columns)
        ]
        if not matches:
            raise QueryValidationError(
                "unknown_column",
                f"Unknown column in query plan: {column_name}.",
            )
        if len(matches) > 1:
            raise QueryValidationError(
                "ambiguous_column",
                f"Column is ambiguous in query plan: {column_name}.",
            )


def _validate_qualified_column(
    table_name: str,
    column_name: str,
    profile: SemanticProfile,
) -> None:
    table = profile.tables.get(table_name)
    if table is None:
        raise QueryValidationError(
            "unknown_table",
            f"Unknown table in query plan: {table_name}.",
        )
    if not any(column.name == column_name for column in table.columns):
        suggestions = [
            f"{candidate_table.name}.{column_name}"
            for candidate_table in profile.tables.values()
            if any(column.name == column_name for column in candidate_table.columns)
        ]
        suggestion_text = (
            f" Use one of: {', '.join(suggestions)}."
            if suggestions
            else ""
        )
        raise QueryValidationError(
            "unknown_column",
            f"Unknown column in query plan: {table_name}.{column_name}."
            f"{suggestion_text}",
        )


def _column_references(expression: str) -> Iterable[tuple[Optional[str], str]]:
    cleaned = re.sub(r"'[^']*'|\"[^\"]*\"", " ", expression)
    cleaned = _OUTPUT_ALIAS.sub("", cleaned)
    qualified = list(_QUALIFIED_IDENTIFIER.finditer(cleaned))
    for match in qualified:
        yield match.group(1), match.group(2)
    masked = _QUALIFIED_IDENTIFIER.sub(" ", cleaned)
    for token in _IDENTIFIER.findall(masked):
        if token.lower() not in _IGNORED_WORDS:
            yield None, token


def _normalize_relationship(value: str) -> str:
    parts = re.split(r"\s*->\s*", value.strip())
    if len(parts) != 2:
        return value.replace(" ", "")
    left = parts[0].strip().replace(" ", "")
    right = parts[1].strip().replace(" ", "")
    return f"{left}->{right}"


def _relationship_key(
    table: str,
    column: str,
    foreign_table: str,
    foreign_column: str,
) -> str:
    return _normalize_relationship(
        f"{table}.{column}->{foreign_table}.{foreign_column}"
    )
