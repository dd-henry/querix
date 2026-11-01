import pytest

from core.query_plan import QueryPlan
from core.query_validation import PlanValidator, QueryValidationError
from core.semantic_context import SemanticProfile


@pytest.fixture
def profile():
    return SemanticProfile.from_metadata(
        {
            "tables": [
                {
                    "name": "orders",
                    "columns": [
                        {"name": "id", "data_type": "integer"},
                        {"name": "amount", "data_type": "numeric"},
                        {"name": "customer_id", "data_type": "integer"},
                    ],
                },
                {
                    "name": "customers",
                    "columns": [
                        {"name": "id", "data_type": "integer"},
                        {"name": "name", "data_type": "text"},
                    ],
                },
            ],
            "relationships": [
                {
                    "table": "orders",
                    "column": "customer_id",
                    "foreign_table": "customers",
                    "foreign_column": "id",
                }
            ],
        }
    )


def _plan(**overrides):
    values = {
        "intent": "customer totals",
        "tables": ("orders", "customers"),
        "relationships": ("orders.customer_id -> customers.id",),
        "dimensions": ("customers.name",),
        "metrics": ("SUM(orders.amount)",),
        "filters": ({"column": "orders.amount", "operator": ">", "value": 0},),
        "grain": "customer",
        "assumptions": ("amount is additive",),
    }
    values.update(overrides)
    return QueryPlan(**values)


def test_valid_generic_plan_passes_against_profile(profile):
    assert PlanValidator.validate_plan(_plan(), profile) == []


def test_existing_columns_allow_inferred_relationship_with_warning(profile):
    warnings = PlanValidator.validate_plan(
        _plan(relationships=("orders.id -> customers.id",)),
        profile,
    )

    assert warnings == [
        "JOIN inferido: orders.id -> customers.id. "
        "Essa relação não está declarada como chave estrangeira no banco."
    ]


def test_metric_output_alias_is_not_validated_as_schema_column(profile):
    PlanValidator.validate_plan(
        _plan(metrics=("SUM(orders.amount) AS total_amount",)),
        profile,
    )


def test_unknown_qualified_column_suggests_matching_schema_columns(profile):
    with pytest.raises(QueryValidationError) as error:
        PlanValidator.validate_plan(
            _plan(dimensions=("orders.name",)),
            profile,
        )

    assert error.value.code == "unknown_column"
    assert "customers.name" in error.value.message


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("tables", ("missing",), "unknown_table"),
        ("dimensions", ("customers.email",), "unknown_column"),
        ("relationships", ("orders.customer_id -> missing.id",), "unknown_relationship"),
        ("relationships", ("orders.missing -> customers.id",), "unknown_relationship"),
    ],
)
def test_unknown_plan_identifiers_have_stable_validation_errors(
    profile,
    field,
    value,
    code,
):
    with pytest.raises(QueryValidationError) as error:
        PlanValidator.validate_plan(_plan(**{field: value}), profile)

    assert error.value.code == code
    assert error.value.message


def test_declared_relationship_in_reverse_direction_has_no_warning(profile):
    assert PlanValidator.validate_plan(
        _plan(relationships=("customers.id -> orders.customer_id",)),
        profile,
    ) == []


def test_repeated_inferred_relationship_has_one_warning(profile):
    warnings = PlanValidator.validate_plan(
        _plan(
            relationships=(
                "orders.id -> customers.id",
                "orders.id -> customers.id",
            )
        ),
        profile,
    )

    assert len(warnings) == 1


def test_sql_validation_accepts_select_and_with():
    assert PlanValidator.validate_sql(" SELECT 1; ") == "SELECT 1"
    assert PlanValidator.validate_sql("WITH values AS (SELECT 1) SELECT * FROM values") == (
        "WITH values AS (SELECT 1) SELECT * FROM values"
    )


@pytest.mark.parametrize("sql", ["DELETE FROM orders", "SELECT 1; SELECT 2"])
def test_sql_validation_rejects_non_read_only_and_multi_statement(sql):
    with pytest.raises(QueryValidationError) as error:
        PlanValidator.validate_sql(sql)

    assert error.value.code == "sql_not_read_only"
