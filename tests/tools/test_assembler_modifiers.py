"""Regression tests for modifier templates in the assembler path."""

from src.codegen.assembler import generate_code


def _modifier_blueprint() -> dict:
    return {
        "description": "modifier test",
        "build_order": ["base", "top_chamfer", "vertical_fillet"],
        "features": {
            "base": {
                "id": "base",
                "type": "box",
                "params": {"x": 100, "y": 80, "z": 20},
                "parent": None,
                "placement": None,
                "operation": "add",
            },
            "top_chamfer": {
                "id": "top_chamfer",
                "type": "chamfer",
                "params": {"size": 2, "edge_selector": "|Z"},
                "parent": "base",
                "placement": {
                    "face": ">Z",
                    "alignment": "centered",
                    "offset_x": 0.0,
                    "offset_y": 0.0,
                    "angle_deg": 0.0,
                },
                "operation": "modify",
            },
            "vertical_fillet": {
                "id": "vertical_fillet",
                "type": "fillet",
                "params": {"radius": 3, "edge_selector": "|Z"},
                "parent": "base",
                "placement": {
                    "face": ">Z",
                    "alignment": "centered",
                    "offset_x": 0.0,
                    "offset_y": 0.0,
                    "angle_deg": 0.0,
                },
                "operation": "modify",
            },
        },
    }


def test_modifier_functions_accept_ref_argument_from_assembly_loop():
    code = generate_code(_modifier_blueprint())

    assert (
        "def make_top_chamfer("
        "body: cq.Workplane, _ref: cq.Workplane | None = None"
    ) in code
    assert (
        "def make_vertical_fillet("
        "body: cq.Workplane, _ref: cq.Workplane | None = None"
    ) in code
    assert "result = make_top_chamfer(result, _ref)" in code
    assert "result = make_vertical_fillet(result, _ref)" in code
