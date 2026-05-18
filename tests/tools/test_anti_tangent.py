"""tests/tools/test_anti_tangent.py — Verify anti-tangent geometry fixes in assembler.

Tangent cuts (slot ends or hole edges sitting mathematically on a parent edge)
produce non-manifold tessellation in OCCT. The assembler nudges them into a
clean state: slots shrink by 0.02mm, tangent holes grow by 0.02mm. See run
0ef217ab for the failing case that motivated this.
"""

from src.codegen.assembler import generate_code


def _bp(features):
    return {
        "build_order": ["wuerfel"] + [f["id"] for f in features],
        "features": {
            "wuerfel": {
                "id": "wuerfel", "type": "box",
                "params": {"x": 100, "y": 100, "z": 100},
                "parent": None, "operation": "add",
            },
            **{f["id"]: f for f in features},
        },
        "description": "test",
    }


class TestSlotAntiTangent:
    def test_slot_default_length_overshoots_parent_edges(self):
        slot = {
            "id": "nut_a", "type": "slot", "operation": "subtract", "parent": "wuerfel",
            "params": {"width": 5, "depth": 5, "length": None},
            "placement": {"face": ">Z", "offset_x": 0, "offset_y": 0,
                          "notes": "entlang x-achse"},
        }
        code = generate_code(_bp([slot]))
        # Mit Mittellinien-Konvention + slot2D-Template (2026-05-18) wird der
        # gerade Slot ebenfalls als slot2D gerendert; der +0.02-Overshoot
        # bleibt wirksam, jetzt halt auf die Endradien-Aussenkontur.
        assert ".slot2D(100.02," in code, "default-length slot should overshoot to 100+0.02"

    def test_slot_explicit_length_is_unchanged(self):
        slot = {
            "id": "nut_b", "type": "slot", "operation": "subtract", "parent": "wuerfel",
            "params": {"width": 5, "depth": 5, "length": 60},
            "placement": {"face": ">Z", "offset_x": 0, "offset_y": 0,
                          "notes": "entlang x-achse"},
        }
        code = generate_code(_bp([slot]))
        assert ".slot2D(60.0," in code
        assert "60.02" not in code, "explicit length must not be modified"


class TestHoleAntiTangent:
    def test_hole_tangent_in_corner_grows(self):
        # ox=-40, r=10, parent=100 → |ox|+r = 50 = parent/2 → tangent in X (and Y)
        hole = {
            "id": "bohr_a", "type": "hole_single", "operation": "subtract", "parent": "wuerfel",
            "params": {"diameter": 20, "depth": 10},
            "placement": {"face": ">Z", "offset_x": -40, "offset_y": 40, "notes": ""},
        }
        code = generate_code(_bp([hole]))
        assert ".circle(10.01)" in code, "tangent hole should grow to d=20.02"

    def test_hole_clearly_inside_unchanged(self):
        hole = {
            "id": "bohr_b", "type": "hole_single", "operation": "subtract", "parent": "wuerfel",
            "params": {"diameter": 20, "depth": 10},
            "placement": {"face": ">Z", "offset_x": 10, "offset_y": 10, "notes": ""},
        }
        code = generate_code(_bp([hole]))
        assert ".circle(10.0)" in code

    def test_hole_clearly_inside_large_centered_unchanged(self):
        hole = {
            "id": "bohr_c", "type": "hole_single", "operation": "subtract", "parent": "wuerfel",
            "params": {"diameter": 80, "depth": 10},
            "placement": {"face": ">Z", "offset_x": 0, "offset_y": 0, "notes": ""},
        }
        code = generate_code(_bp([hole]))
        assert ".circle(40.0)" in code

    def test_hole_tangent_on_side_face(self):
        # Same tangent rule on side faces — uses parent (y, z) for face <X
        hole = {
            "id": "bohr_d", "type": "hole_single", "operation": "subtract", "parent": "wuerfel",
            "params": {"diameter": 20, "depth": 10},
            "placement": {"face": "<X", "offset_x": -40, "offset_y": 40, "notes": ""},
        }
        code = generate_code(_bp([hole]))
        assert ".circle(10.01)" in code
