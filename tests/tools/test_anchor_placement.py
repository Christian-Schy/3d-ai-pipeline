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


# ─── Bug 7 (ADR 0004): Edge-endpoint anchor keywords ─────────────────


def test_right_edge_bottom_endpoint_resolves_to_corner():
    """parent_point='right_edge_bottom' is right_edge midpoint shifted to bottom.

    Parent 50x50 → right_edge_bottom at (+0.5, -0.5) → (+25, -25).
    Child 40x40 centered on parent center → child_point='center' at (0, 0).
    offset = parent_pt - child_pt = (25, -25).
    """
    bp = _base_two_part_blueprint({
        "side": "oben",
        "alignment": "centered",
        "anchor": {
            "child_point": "center",
            "parent_point": "right_edge_bottom",
        },
    })
    resolved = resolve_blueprint(bp)
    pl = resolved["features"]["plate"]["placement"]
    assert pl["offset_x"] == 25.0
    assert pl["offset_y"] == -25.0


def test_corner_on_edge_endpoint_with_offset():
    """Real-run da35a6ce equivalent: bottom_right child corner on right_edge_bottom
    of parent, plus 10mm up.

    Parent 50x50 → right_edge_bottom at (+25, -25).
    Child 40x40 → bottom_right at (+0.5, -0.5) → (+20, -20).
    offset = parent - child = (5, -5), then +10 up (y) = (5, +5).
    """
    bp = _base_two_part_blueprint({
        "side": "oben",
        "alignment": "centered",
        "anchor": {
            "child_point": "bottom_right",
            "parent_point": "right_edge_bottom",
            "offset": {"up": 10},
        },
    })
    resolved = resolve_blueprint(bp)
    pl = resolved["features"]["plate"]["placement"]
    assert pl["offset_x"] == 5.0
    assert pl["offset_y"] == 5.0


def test_german_endpoint_alias_resolves():
    """German alias 'rechte_kante_unten' must behave identically to 'right_edge_bottom'."""
    bp = _base_two_part_blueprint({
        "side": "oben",
        "alignment": "centered",
        "anchor": {
            "child_point": "center",
            "parent_point": "rechte_kante_unten",
        },
    })
    resolved = resolve_blueprint(bp)
    pl = resolved["features"]["plate"]["placement"]
    assert pl["offset_x"] == 25.0
    assert pl["offset_y"] == -25.0


def test_endpoint_h_flip_on_negY_face():
    """On <Y face, viewer convention is NOT flipped (face is in _FACE_VIEWER_H_FLIP=False).

    The da35a6ce real-run uses the <Y face. parent_point='right_edge_bottom' must
    map to the SAME face-local coords (+0.5, -0.5). Verifies no spurious flip.
    """
    bp = _base_two_part_blueprint({
        "side": "vorne",  # → <Y on standard cube
        "alignment": "centered",
        "anchor": {
            "child_point": "center",
            "parent_point": "right_edge_bottom",
        },
    })
    resolved = resolve_blueprint(bp)
    pl = resolved["features"]["plate"]["placement"]
    assert pl["face"] == "<Y"
    # Parent 50x50 face on <Y: face_w along X (+0.5 → +25), face_h along Z (-0.5 → -25)
    assert pl["offset_x"] == 25.0
    assert pl["offset_y"] == -25.0


def test_endpoint_h_flip_on_negX_face():
    """On <X face, viewer convention IS flipped (left↔right).

    parent_point='right_edge_bottom' (viewer-right) must flip to LUT 'left_edge_bottom'
    so the resolved offset lands at viewer-right of the parent.
    Parent 50x50 face on <X: face_w along Y, face_h along Z.
    LUT 'left_edge_bottom' = (-0.5, -0.5) → world wx=-25, wy=-25.
    """
    bp = _base_two_part_blueprint({
        "side": "links",  # → <X
        "alignment": "centered",
        "anchor": {
            "child_point": "center",
            "parent_point": "right_edge_bottom",
        },
    })
    resolved = resolve_blueprint(bp)
    pl = resolved["features"]["plate"]["placement"]
    assert pl["face"] == "<X"
    # After flip → -25 along face_w axis, -25 along face_h axis
    assert pl["offset_x"] == -25.0
    assert pl["offset_y"] == -25.0


def test_real_run_da35a6ce_plate_position():
    """Smoke test for ADR 0004 reference case.

    Parent 200x200x200 cube, child 140x20x40 plate on <Y face.
    Plate's 140x20 side touches the cube → orientation puts (140, 40) into the
    face plane (face_w=140 along X, face_h=40 along Z).

    User: "rechte untere ecke auf der rechten kante 10mm nach oben, 20° CCW"
    → child_point=bottom_right (=(+0.5, -0.5) of plate face = (+70, -20))
    → parent_point=right_edge_bottom (=(+0.5, -0.5) of cube face = (+100, -100))
    → angle_deg=20 (CCW)
    Expected after pre-rotation of child anchor offset by 20°:
        rotated_child = (70*cos20 - (-20)*sin20, 70*sin20 + (-20)*cos20)
                      ≈ (72.62, 5.15)
        offset = parent - rotated_child = (100 - 72.62, -100 - 5.15)
               ≈ (27.38, -105.15)
    Then +10mm up → (27.38, -95.15).
    """
    import math
    bp = {
        "description": "real-run da35a6ce",
        "build_order": ["wuerfel", "platte"],
        "features": {
            "wuerfel": {
                "type": "box",
                "params": {"x": 200, "y": 200, "z": 200},
                "orientation": "standard",
                "parent": None,
                "operation": "add",
            },
            "platte": {
                "type": "box",
                "params": {"x": 140, "y": 20, "z": 40},
                "orientation": "140x40_liegt_auf",
                "parent": "wuerfel",
                "position": {
                    "side": "vorne",
                    "alignment": "centered",
                    "angle_deg": 20.0,
                    "anchor": {
                        "child_point": "bottom_right",
                        "parent_point": "right_edge_bottom",
                        "offset": {"up": 10},
                    },
                },
                "operation": "add",
            },
        },
    }
    resolved = resolve_blueprint(bp)
    pl = resolved["features"]["platte"]["placement"]
    assert pl["face"] == "<Y"
    # Math: plate face on <Y after 140x40_liegt_auf → face_w=140, face_h=40.
    # child bottom_right = (+70, -20); rotate by 20° CCW.
    a = math.radians(20)
    rx = 70 * math.cos(a) - (-20) * math.sin(a)
    ry = 70 * math.sin(a) + (-20) * math.cos(a)
    expected_ox = round(100 - rx, 4)
    expected_oy = round(-100 - ry + 10, 4)
    assert abs(pl["offset_x"] - expected_ox) < 0.01
    assert abs(pl["offset_y"] - expected_oy) < 0.01
