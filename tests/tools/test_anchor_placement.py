"""Tests for SemanticAnchor end-to-end: resolver → assembler code output.

Covers:
- Center-on-center default (empty anchor dict) preserves legacy behavior.
- Corner-on-edge placement produces the expected offset math.
- pre_rotation passes through the resolver and lands as .rotate() in code.
"""
from __future__ import annotations

from src.tools.blueprint_resolver import resolve_blueprint
from src.codegen.assembler import generate_code


def _base_two_part_blueprint(child_position: dict) -> dict:
    return {
        "description": "test",
        "build_order": ["cube", "plate"],
        "features": {
            "cube": {
                "type": "box",
                "params": {"x": 50, "y": 50, "z": 50},
                "orientation": "standard",
                "parent": None,
                "operation": "add",
            },
            "plate": {
                "type": "box",
                "params": {"x": 40, "y": 40, "z": 20},
                "orientation": "standard",
                "parent": "cube",
                "position": child_position,
                "operation": "add",
            },
        },
    }


def test_empty_anchor_is_centered():
    """anchor={} → child center on parent center → offset (0, 0)."""
    bp = _base_two_part_blueprint({
        "side": "oben",
        "alignment": "centered",
        "anchor": {},
    })
    resolved = resolve_blueprint(bp)
    plate = resolved["features"]["plate"]
    assert plate["placement"]["offset_x"] == 0.0
    assert plate["placement"]["offset_y"] == 0.0
    assert plate["placement"]["face"] == ">Z"


def test_corner_on_edge_anchor_offset():
    """top_left of child on left_edge of parent (both on >Z face).

    Parent 50x50 → left_edge center at (wx=-0.5, wy=0) → (-25, 0).
    Child 40x40 → top_left at (wx=-0.5, wy=+0.5) → (-20, +20).
    offset = parent_pt - child_pt = (-25 - (-20), 0 - 20) = (-5, -20).
    """
    bp = _base_two_part_blueprint({
        "side": "oben",
        "alignment": "centered",
        "anchor": {
            "child_point": "top_left",
            "parent_point": "left_edge",
        },
    })
    resolved = resolve_blueprint(bp)
    pl = resolved["features"]["plate"]["placement"]
    assert pl["offset_x"] == -5.0
    assert pl["offset_y"] == -20.0


def test_anchor_offset_additive():
    """anchor.offset shifts further after anchoring."""
    bp = _base_two_part_blueprint({
        "side": "oben",
        "alignment": "centered",
        "anchor": {
            "child_point": "top_left",
            "parent_point": "left_edge",
            "offset": {"down": 10},
        },
    })
    resolved = resolve_blueprint(bp)
    pl = resolved["features"]["plate"]["placement"]
    # 'down' on >Z face maps to bottom (negative Y)
    assert pl["offset_x"] == -5.0
    assert pl["offset_y"] == -30.0


def test_pre_rotation_emits_rotate_call():
    """pre_rotation.z = -10 should produce body.rotate(...) in generated code."""
    bp = _base_two_part_blueprint({
        "side": "oben",
        "alignment": "centered",
        "anchor": {
            "child_point": "top_left",
            "parent_point": "left_edge",
            "pre_rotation": {"z": -10},
        },
    })
    resolved = resolve_blueprint(bp)
    pl = resolved["features"]["plate"]["placement"]
    assert pl["pre_rotation"] == {"z": -10}

    code = generate_code(resolved)
    # Find the rotate call before translate
    assert "plate.rotate((0, 0, 0), (0, 0, 1), -10.0)" in code
    # translate must still appear
    assert "plate.translate(" in code


def test_no_pre_rotation_emits_no_rotate():
    """Absent pre_rotation → no .rotate() call in generated code."""
    bp = _base_two_part_blueprint({
        "side": "oben",
        "alignment": "centered",
    })
    resolved = resolve_blueprint(bp)
    code = generate_code(resolved)
    assert ".rotate(" not in code
