"""Tests for assembler rotation emission (angle_deg + pre_rotation on sub-assembly adds)."""

from src.codegen.assembler import generate_code


def _blueprint_two_parts(angle_deg: float = 0.0, face: str = ">Z") -> dict:
    """Parent box + child box placed on a face with optional angle_deg."""
    return {
        "description": "test",
        "build_order": ["parent", "child"],
        "features": {
            "parent": {
                "id": "parent",
                "type": "box",
                "params": {"x": 100, "y": 100, "z": 20},
                "parent": None,
                "placement": None,
                "operation": "add",
                "notes": "",
            },
            "child": {
                "id": "child",
                "type": "box",
                "params": {"x": 50, "y": 50, "z": 50},
                "parent": "parent",
                "placement": {
                    "face": face,
                    "alignment": "centered",
                    "offset_x": 0.0,
                    "offset_y": 0.0,
                    "angle_deg": angle_deg,
                    "pre_rotation": None,
                    "notes": "",
                },
                "operation": "add",
                "notes": "",
            },
        },
    }


def test_angle_deg_45_on_top_face_emits_rotate_call():
    # Regression for Run 823b07fe: box on >Z with 45° was not rotating.
    code = generate_code(_blueprint_two_parts(angle_deg=45.0, face=">Z"))
    assert ".rotate(" in code
    assert "45" in code
    # Rotation must happen BEFORE the .translate() line for the child.
    rotate_idx = code.index(".rotate(")
    translate_idx = code.index(".translate(")
    assert rotate_idx < translate_idx


def test_angle_deg_zero_omits_rotate():
    code = generate_code(_blueprint_two_parts(angle_deg=0.0, face=">Z"))
    # No rotate call for the sub-assembly when angle is zero
    assert ".rotate(" not in code


def test_angle_deg_on_right_face_uses_x_axis():
    # Regression for Run 4e2fd4ab: plate on >X with 10° must rotate around X.
    code = generate_code(_blueprint_two_parts(angle_deg=10.0, face=">X"))
    # Axis through centroid for >X: second point has nonzero X component.
    assert ".rotate((0, 0, CHILD_Z/2), (1, 0, CHILD_Z/2), 10" in code
