"""Tests for hole_pattern_circular start_angle_deg emission.

Quick-Win 2026-05-19: 'erste Bohrung bei 0/90 Grad' / 'Startwinkel 45 Grad'
should propagate via params.start_angle_deg into the polarArray template.
"""

from src.codegen.assembler import generate_code


def _blueprint_lochkreis(start_angle_deg: float | None = None) -> dict:
    params = {
        "hole_diameter": 5,
        "depth": 4,
        "count": 6,
        "bolt_circle_diameter": 50,
    }
    if start_angle_deg is not None:
        params["start_angle_deg"] = start_angle_deg
    return {
        "description": "test",
        "build_order": ["wuerfel", "m_circ"],
        "features": {
            "wuerfel": {
                "id": "wuerfel",
                "type": "box",
                "params": {"x": 100, "y": 100, "z": 50},
                "parent": None,
                "placement": None,
                "operation": "add",
            },
            "m_circ": {
                "id": "m_circ",
                "type": "hole_pattern_circular",
                "params": params,
                "parent": "wuerfel",
                "placement": {
                    "face": ">Z",
                    "alignment": "centered",
                    "offset_x": 0.0,
                    "offset_y": 0.0,
                    "angle_deg": 0.0,
                },
                "operation": "subtract",
            },
        },
    }


def test_default_start_angle_zero():
    code = generate_code(_blueprint_lochkreis())
    # polarArray with start_angle 0.0
    assert ".polarArray(25.0, 0.0, 360, 6)" in code


def test_explicit_start_angle_90():
    code = generate_code(_blueprint_lochkreis(start_angle_deg=90.0))
    assert ".polarArray(25.0, 90.0, 360, 6)" in code


def test_explicit_start_angle_45():
    code = generate_code(_blueprint_lochkreis(start_angle_deg=45.0))
    assert ".polarArray(25.0, 45.0, 360, 6)" in code
