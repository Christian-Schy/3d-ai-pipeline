"""tests/graph/test_coord_validator_node.py

Bug 3 (Run e3ddd2d0) regression: coord_validator_node trace must carry
the actual issue messages (not just counts), and runs that hit max_retries
with errors still present must set coordinate_errors_unresolved=True so
post-mortem analysis can flag the run as "STL produced but with known
geometry violations".
"""
from __future__ import annotations

from src.graph.nodes.planning_nodes import coordinate_validator_node


def _bp_with_oversize_pocket() -> dict:
    """Pocket bigger than its parent face — guaranteed ERROR."""
    return {
        "build_order": ["wuerfel", "tasche"],
        "features": {
            "wuerfel": {
                "id": "wuerfel", "type": "box",
                "params": {"x": 50, "y": 50, "z": 50},
                "orientation": "standard",
                "parent": None, "operation": "add",
            },
            "tasche": {
                "id": "tasche", "type": "pocket_rect",
                "params": {"x": 200, "y": 200, "depth": 5},
                "orientation": "standard",
                "parent": "wuerfel", "operation": "subtract",
                "placement": {"face": ">Z", "alignment": "centered",
                              "offset_x": 0, "offset_y": 0,
                              "angle_deg": 0.0, "pre_rotation": None,
                              "notes": ""},
            },
        },
    }


def _bp_clean() -> dict:
    """Tiny pocket on a big cube — no errors."""
    return {
        "build_order": ["wuerfel", "tasche"],
        "features": {
            "wuerfel": {
                "id": "wuerfel", "type": "box",
                "params": {"x": 200, "y": 200, "z": 200},
                "orientation": "standard",
                "parent": None, "operation": "add",
            },
            "tasche": {
                "id": "tasche", "type": "pocket_rect",
                "params": {"x": 20, "y": 20, "depth": 5},
                "orientation": "standard",
                "parent": "wuerfel", "operation": "subtract",
                "placement": {"face": ">Z", "alignment": "centered",
                              "offset_x": 0, "offset_y": 0,
                              "angle_deg": 0.0, "pre_rotation": None,
                              "notes": ""},
            },
        },
    }


def test_trace_carries_issue_text_on_error():
    state = {"blueprint": _bp_with_oversize_pocket(), "agent_traces": []}
    result = coordinate_validator_node(state)

    assert result["coordinate_valid"] is False
    trace = result["agent_traces"][0]
    out = trace["output"]
    assert out["errors"] >= 1
    # The actual issue text must be in the trace, not just a count
    assert "issues" in out
    assert isinstance(out["issues"], list)
    assert len(out["issues"]) >= 1
    # Message format: "[ERROR] feature_id — check: message"
    first = out["issues"][0]
    assert "ERROR" in first
    assert "tasche" in first


def test_first_failure_does_not_swallow():
    """Attempt 1 of 2 → still room to retry → unresolved=False."""
    state = {"blueprint": _bp_with_oversize_pocket(), "agent_traces": [],
             "coordinate_validation_attempts": 0}
    result = coordinate_validator_node(state)

    out = result["agent_traces"][0]["output"]
    assert out["attempts"] == 1
    assert out["unresolved_at_max_retries"] is False
    assert result.get("coordinate_errors_unresolved") is False


def test_max_retries_marks_swallowed():
    """When attempts reach max_retries with errors still there, the node
    sets coordinate_errors_unresolved=True for downstream visibility."""
    state = {"blueprint": _bp_with_oversize_pocket(), "agent_traces": [],
             # already at max_retries - 1; this call increments to max
             "coordinate_validation_attempts": 1}
    result = coordinate_validator_node(state)

    out = result["agent_traces"][0]["output"]
    assert out["attempts"] >= 2
    assert out["unresolved_at_max_retries"] is True
    assert result["coordinate_errors_unresolved"] is True


def test_clean_blueprint_no_issues_in_trace():
    state = {"blueprint": _bp_clean(), "agent_traces": []}
    result = coordinate_validator_node(state)

    assert result["coordinate_valid"] is True
    out = result["agent_traces"][0]["output"]
    assert out["errors"] == 0
    # `issues` list still exists but is empty
    assert out.get("issues", []) == []
