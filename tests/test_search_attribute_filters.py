"""Unit tests for `_attribute_predicates` (PLAN retrieval P1-9)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from capability_commons.db.models import ContextObject, ContextObjectVersion
from capability_commons.schemas.search import PublicSearchFilters
from capability_commons.search.adapters.postgres_search import _attribute_predicates


def _compile(predicates) -> str:
    """Render a list of predicates as a SQL WHERE fragment for assertion."""
    if not predicates:
        return ""
    stmt = select(ContextObjectVersion.id).join(
        ContextObject, ContextObjectVersion.context_object_id == ContextObject.id
    )
    for p in predicates:
        stmt = stmt.where(p)
    compiled = stmt.compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": True},
    )
    return str(compiled)


def test_no_filters_yields_no_predicates():
    assert _attribute_predicates(None) == []
    assert _attribute_predicates(PublicSearchFilters()) == []


def test_difficulty_max_constrains_difficulty():
    sql = _compile(_attribute_predicates(PublicSearchFilters(difficulty_max=2)))
    assert "context_object_versions.difficulty <= 2" in sql


def test_stage_constrains_stage_column():
    sql = _compile(_attribute_predicates(PublicSearchFilters(stage="household")))
    assert "context_object_versions.stage" in sql
    assert "HOUSEHOLD" in sql.upper() or "household" in sql.lower()


def test_invalid_stage_is_silently_dropped():
    # A bogus stage value must not raise; it's just ignored.
    preds = _attribute_predicates(PublicSearchFilters(stage="not-a-stage"))
    assert preds == []


def test_risk_band_caps_at_or_below_target():
    sql = _compile(_attribute_predicates(PublicSearchFilters(risk_band="moderate")))
    # Should permit low and moderate, exclude high and expert_only.
    assert "context_object_versions.risk_band IN" in sql
    assert "low" in sql.lower() and "moderate" in sql.lower()
    assert "expert_only" not in sql.lower()


def test_beginner_safe_caps_risk_and_difficulty():
    sql = _compile(_attribute_predicates(PublicSearchFilters(beginner_safe=True)))
    # risk_band capped to ≤ moderate
    assert "risk_band IN" in sql
    assert "expert_only" not in sql.lower()
    # difficulty capped to ≤ 3 when caller didn't specify
    assert "context_object_versions.difficulty <= 3" in sql


def test_beginner_safe_respects_explicit_difficulty():
    sql = _compile(_attribute_predicates(
        PublicSearchFilters(beginner_safe=True, difficulty_max=2)
    ))
    assert "context_object_versions.difficulty <= 2" in sql
    # Should NOT emit a second `difficulty <= 3` clause.
    assert sql.count("difficulty <=") == 1


def test_cost_band_caps_below_target():
    sql = _compile(_attribute_predicates(PublicSearchFilters(cost_band="low")))
    assert "context_object_versions.cost_band IN" in sql
    assert "free" in sql.lower() and "low" in sql.lower()
    assert "high" not in sql.lower() or sql.lower().count("high") == 0


def test_language_code_filter_emits_equality(tmp_path=None):
    """MULTI-1: language_code filter narrows by exact match."""
    sql = _compile(_attribute_predicates(PublicSearchFilters(language_code="es")))
    assert "context_object_versions.language_code = 'es'" in sql


def test_language_code_none_emits_no_clause():
    sql = _compile(_attribute_predicates(PublicSearchFilters(language_code=None)))
    assert "language_code" not in sql
