import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from database.base import DatabaseAdapter


_TEMPORAL_TYPES = (
    "date",
    "time",
    "timestamp",
)
_NUMERIC_TYPES = (
    "bigint",
    "decimal",
    "double precision",
    "integer",
    "money",
    "numeric",
    "real",
    "smallint",
)


@dataclass(frozen=True)
class ColumnProfile:
    name: str
    data_type: str
    nullable: bool
    is_primary_key: bool = False
    is_unique: bool = False
    comment: Optional[str] = None

    @property
    def is_temporal(self) -> bool:
        normalized_type = self.data_type.strip().lower()
        return any(
            normalized_type == candidate
            or normalized_type.startswith(f"{candidate} ")
            for candidate in _TEMPORAL_TYPES
        )

    @property
    def is_numeric(self) -> bool:
        normalized_type = self.data_type.strip().lower()
        return normalized_type in _NUMERIC_TYPES or normalized_type.startswith(
            ("bigint", "decimal", "integer", "numeric", "real", "smallint")
        )


@dataclass(frozen=True)
class TableProfile:
    name: str
    columns: tuple[ColumnProfile, ...]
    comment: Optional[str] = None

    @property
    def candidate_temporal_columns(self) -> tuple[str, ...]:
        return tuple(column.name for column in self.columns if column.is_temporal)

    @property
    def candidate_numeric_columns(self) -> tuple[str, ...]:
        return tuple(column.name for column in self.columns if column.is_numeric)


@dataclass(frozen=True)
class RelationshipProfile:
    table: str
    column: str
    foreign_table: str
    foreign_column: str


@dataclass(frozen=True)
class SemanticProfile:
    tables: dict[str, TableProfile]
    relationships: tuple[RelationshipProfile, ...]
    generated_at: datetime

    @classmethod
    def from_metadata(
        cls,
        metadata: Optional[Mapping[str, object]],
        generated_at: Optional[datetime] = None,
    ) -> "SemanticProfile":
        tables: dict[str, TableProfile] = {}
        relationships: list[RelationshipProfile] = []
        metadata = metadata if isinstance(metadata, Mapping) else {}

        for raw_table in _iter_table_metadata(metadata.get("tables")):
            table_name = _text(raw_table.get("name") or raw_table.get("table_name"))
            if not table_name:
                continue

            columns: list[ColumnProfile] = []
            raw_columns = raw_table.get("columns")
            if isinstance(raw_columns, Sequence) and not isinstance(
                raw_columns, (str, bytes)
            ):
                for raw_column in raw_columns:
                    if not isinstance(raw_column, Mapping):
                        continue
                    column_name = _text(
                        raw_column.get("name") or raw_column.get("column_name")
                    )
                    data_type = _text(
                        raw_column.get("data_type") or raw_column.get("type")
                    )
                    if not column_name or not data_type:
                        continue
                    columns.append(
                        ColumnProfile(
                            name=column_name,
                            data_type=data_type,
                            nullable=_nullable(raw_column),
                            is_primary_key=bool(raw_column.get("is_primary_key")),
                            is_unique=bool(raw_column.get("is_unique")),
                            comment=_optional_text(
                                raw_column.get("comment")
                                or raw_column.get("column_comment")
                            ),
                        )
                    )

            tables[table_name] = TableProfile(
                name=table_name,
                columns=tuple(columns),
                comment=_optional_text(
                    raw_table.get("comment") or raw_table.get("table_comment")
                ),
            )

        raw_relationships = metadata.get("relationships")
        if isinstance(raw_relationships, Sequence) and not isinstance(
            raw_relationships, (str, bytes)
        ):
            for raw_relationship in raw_relationships:
                if not isinstance(raw_relationship, Mapping):
                    continue
                table = _text(
                    raw_relationship.get("table")
                    or raw_relationship.get("table_name")
                )
                column = _text(
                    raw_relationship.get("column")
                    or raw_relationship.get("column_name")
                )
                foreign_table = _text(
                    raw_relationship.get("foreign_table")
                    or raw_relationship.get("foreign_table_name")
                )
                foreign_column = _text(
                    raw_relationship.get("foreign_column")
                    or raw_relationship.get("foreign_column_name")
                )
                if table and column and foreign_table and foreign_column:
                    relationships.append(
                        RelationshipProfile(
                            table=table,
                            column=column,
                            foreign_table=foreign_table,
                            foreign_column=foreign_column,
                        )
                    )

        return cls(
            tables=tables,
            relationships=tuple(relationships),
            generated_at=generated_at or datetime.now(timezone.utc),
        )

    def to_prompt_context(self) -> str:
        """Serializa apenas estrutura segura para uso no contexto do modelo."""
        lines: list[str] = []
        for table in self.tables.values():
            comment = f" -- Comentário: {table.comment}" if table.comment else ""
            lines.append(f"Tabela: {table.name}{comment}")
            for column in table.columns:
                details = [column.data_type]
                if not column.nullable:
                    details.append("não nulo")
                if column.is_primary_key:
                    details.append("chave primária")
                elif column.is_unique:
                    details.append("único")
                if column.comment:
                    details.append(f"comentário: {column.comment}")
                lines.append(f"  - {column.name} ({', '.join(details)})")
            if table.candidate_temporal_columns:
                lines.append(
                    "  - Candidatas temporais: "
                    + ", ".join(table.candidate_temporal_columns)
                )
            if table.candidate_numeric_columns:
                lines.append(
                    "  - Candidatas numéricas: "
                    + ", ".join(table.candidate_numeric_columns)
                )

        if self.relationships:
            lines.append("Relacionamentos (chaves estrangeiras):")
            lines.extend(
                f"  - {relationship.table}.{relationship.column} -> "
                f"{relationship.foreign_table}.{relationship.foreign_column}"
                for relationship in self.relationships
            )
        return "\n".join(lines)


class SemanticContextService:
    def __init__(self, database: DatabaseAdapter):
        self._database = database
        self._profile: Optional[SemanticProfile] = None

    def get_profile(self) -> SemanticProfile:
        if self._profile is None:
            metadata = self._database.get_schema_metadata()
            if not isinstance(metadata, Mapping):
                metadata = {}
            self._profile = SemanticProfile.from_metadata(metadata)
        return self._profile

    def invalidate(self) -> None:
        self._profile = None


def _iter_table_metadata(value: object) -> Sequence[Mapping[str, object]]:
    if isinstance(value, Mapping):
        items: list[Mapping[str, object]] = []
        for name, table in value.items():
            if isinstance(table, Mapping):
                items.append({"name": name, **table})
        return items
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _optional_text(value: object) -> Optional[str]:
    text = _text(value)
    return text or None


def _nullable(column: Mapping[str, object]) -> bool:
    if "nullable" in column:
        return bool(column["nullable"])
    return str(column.get("is_nullable", "")).upper() != "NO"
