from pathlib import Path

from capability_commons.cli.seed import (
    SEED_EDGE_TO_EDGE_TYPE,
    SEED_TYPE_TO_CO_TYPE,
    build_structured_data,
    load_edges,
    load_yaml_nodes,
    map_facets,
)
from capability_commons.domain.enums import COType, EdgeType, FacetType
from capability_commons.schemas.structured_data import (
    AssessmentStructuredData,
    ModuleStructuredData,
    validate_structured_data,
)

SEED_DIR = Path(__file__).resolve().parents[1] / "expanded_seed"
MODULE_SEED_DIR = Path(__file__).resolve().parents[1] / "capability_commons_module_seed_pack_v1"


# === Base 25-node seed tests ===


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


def test_load_edges_base():
    edges = load_edges(SEED_DIR)
    assert len(edges) == 77  # 50 REQUIRES + 27 NEXT
    edge_types = {e["edge_type"] for e in edges}
    assert "REQUIRES" in edge_types
    assert "NEXT" in edge_types


def test_map_co_type_base():
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


# === Module seed pack v1 tests ===


def test_map_co_type_curriculum():
    assert SEED_TYPE_TO_CO_TYPE["module"] == COType.MODULE
    assert SEED_TYPE_TO_CO_TYPE["assessment"] == COType.ASSESSMENT


def test_edge_type_mappings():
    assert SEED_EDGE_TO_EDGE_TYPE["REQUIRES"] == EdgeType.PREREQUISITE_FOR
    assert SEED_EDGE_TO_EDGE_TYPE["NEXT"] == EdgeType.NEXT_STEP_FOR
    assert SEED_EDGE_TO_EDGE_TYPE["COVERS"] == EdgeType.CONTAINS
    assert SEED_EDGE_TO_EDGE_TYPE["ASSESSED_BY"] == EdgeType.ASSESSED_BY
    assert SEED_EDGE_TO_EDGE_TYPE["EVALUATES"] == EdgeType.VALIDATED_BY
    assert SEED_EDGE_TO_EDGE_TYPE["PRECEDES"] == EdgeType.NEXT_STEP_FOR


def test_load_module_seed_yaml_count():
    nodes = load_yaml_nodes(MODULE_SEED_DIR)
    assert len(nodes) == 24  # 12 modules + 12 assessments


def test_load_module_seed_yaml_types():
    nodes = load_yaml_nodes(MODULE_SEED_DIR)
    types = {n["type"] for n in nodes}
    assert types == {"module", "assessment"}
    modules = [n for n in nodes if n["type"] == "module"]
    assessments = [n for n in nodes if n["type"] == "assessment"]
    assert len(modules) == 12
    assert len(assessments) == 12


def test_load_module_seed_yaml_required_fields():
    nodes = load_yaml_nodes(MODULE_SEED_DIR)
    for node in nodes:
        assert "id" in node
        assert "type" in node
        assert "title" in node
        assert "plain_language" in node
        assert "payload" in node
        assert node["type"] in SEED_TYPE_TO_CO_TYPE


def test_module_payload_has_required_fields():
    nodes = load_yaml_nodes(MODULE_SEED_DIR)
    modules = [n for n in nodes if n["type"] == "module"]
    for mod in modules:
        payload = mod["payload"]
        assert "week" in payload
        assert "node_refs" in payload
        assert "learning_objectives" in payload
        assert "seminar_outline" in payload
        assert "lab" in payload
        assert "field_task" in payload
        assert "teach_forward_task" in payload
        assert "assessment_ref" in payload
        assert "delivery_profile" in payload


def test_assessment_payload_has_required_fields():
    nodes = load_yaml_nodes(MODULE_SEED_DIR)
    assessments = [n for n in nodes if n["type"] == "assessment"]
    for asmt in assessments:
        payload = asmt["payload"]
        assert "assessment_type" in payload
        assert "rubric" in payload
        assert "passing_threshold" in payload
        assert "evidence_required" in payload


def test_module_structured_data_validates():
    """Module seed YAML payloads should pass ModuleStructuredData validation."""
    nodes = load_yaml_nodes(MODULE_SEED_DIR)
    modules = [n for n in nodes if n["type"] == "module"]
    for mod in modules:
        sd = build_structured_data(mod)
        validated = validate_structured_data(COType.MODULE, sd)
        assert validated["week"] == mod["payload"]["week"]
        assert validated["node_refs"] == mod["payload"]["node_refs"]


def test_assessment_structured_data_validates():
    """Assessment seed YAML payloads should pass AssessmentStructuredData validation."""
    nodes = load_yaml_nodes(MODULE_SEED_DIR)
    assessments = [n for n in nodes if n["type"] == "assessment"]
    for asmt in assessments:
        sd = build_structured_data(asmt)
        validated = validate_structured_data(COType.ASSESSMENT, sd)
        assert validated["assessment_type"] == asmt["payload"]["assessment_type"]
        assert validated["rubric"] == asmt["payload"]["rubric"]


def test_load_module_seed_edges():
    edges = load_edges(MODULE_SEED_DIR)
    assert len(edges) == 98
    edge_types = {e["edge_type"] for e in edges}
    assert edge_types == {"REQUIRES", "COVERS", "ASSESSED_BY", "EVALUATES", "PRECEDES"}


def test_load_module_seed_edge_counts():
    edges = load_edges(MODULE_SEED_DIR)
    counts = {}
    for e in edges:
        counts[e["edge_type"]] = counts.get(e["edge_type"], 0) + 1
    assert counts["REQUIRES"] == 25
    assert counts["COVERS"] == 25
    assert counts["ASSESSED_BY"] == 12
    assert counts["EVALUATES"] == 25
    assert counts["PRECEDES"] == 11


def test_all_module_edge_types_have_mappings():
    edges = load_edges(MODULE_SEED_DIR)
    for e in edges:
        assert e["edge_type"] in SEED_EDGE_TO_EDGE_TYPE, f"Unmapped edge type: {e['edge_type']}"


def test_module_facets():
    nodes = load_yaml_nodes(MODULE_SEED_DIR)
    mod1 = next(n for n in nodes if n["id"] == "module.01-truth-tools-and-ai")
    facets = map_facets(mod1)
    assert (FacetType.DOMAIN, "foundation") in facets
    assert (FacetType.AUDIENCE, "general") in facets
    assert (FacetType.AUDIENCE, "renter") in facets
    assert (FacetType.SETTLEMENT_TYPE, "urban") in facets
