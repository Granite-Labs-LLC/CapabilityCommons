from pathlib import Path

from capability_commons.cli.seed import (
    SEED_TYPE_TO_CO_TYPE,
    build_structured_data,
    load_next_edges,
    load_yaml_nodes,
    map_facets,
)
from capability_commons.domain.enums import COType, FacetType

SEED_DIR = Path(__file__).resolve().parents[1] / "expanded_seed"


def test_load_yaml_nodes_count():
    nodes = load_yaml_nodes(SEED_DIR)
    assert len(nodes) == 25


def test_load_yaml_nodes_has_required_fields():
    nodes = load_yaml_nodes(SEED_DIR)
    for node in nodes:
        assert "id" in node
        assert "type" in node
        assert "title" in node
        assert "plain_language" in node
        assert node["type"] in SEED_TYPE_TO_CO_TYPE


def test_load_next_edges():
    edges = load_next_edges(SEED_DIR)
    assert len(edges) == 27  # 77 total - 50 REQUIRES = 27 NEXT
    for e in edges:
        assert e["edge_type"] == "NEXT"


def test_map_co_type():
    assert SEED_TYPE_TO_CO_TYPE["skill"] == COType.SKILL_GUIDE
    assert SEED_TYPE_TO_CO_TYPE["concept"] == COType.CONCEPT_NOTE
    assert SEED_TYPE_TO_CO_TYPE["project"] == COType.PROJECT_BLUEPRINT


def test_map_facets():
    node = {
        "primary_domain": "water",
        "contexts": ["general", "renter", "urban", "low_budget"],
    }
    facets = map_facets(node)
    assert (FacetType.DOMAIN, "water") in facets
    assert (FacetType.AUDIENCE, "general") in facets
    assert (FacetType.AUDIENCE, "renter") in facets
    assert (FacetType.SETTLEMENT_TYPE, "urban") in facets
    assert (FacetType.BUDGET_PROFILE, "low_budget") in facets


def test_build_structured_data():
    node = {
        "payload": {"performance_statement": "Do the thing", "tools": ["hammer"]},
        "tags": ["repair", "tools"],
        "outputs": ["checklist"],
    }
    sd = build_structured_data(node)
    assert sd["performance_statement"] == "Do the thing"
    assert sd["tools"] == ["hammer"]
    assert sd["tags"] == ["repair", "tools"]
    assert sd["outputs"] == ["checklist"]


def test_build_structured_data_no_payload():
    node = {"tags": ["a"]}
    sd = build_structured_data(node)
    assert sd["tags"] == ["a"]
    assert "performance_statement" not in sd
