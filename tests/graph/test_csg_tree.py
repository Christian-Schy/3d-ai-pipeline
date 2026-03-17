"""
tests/graph/test_csg_tree.py — Tests for the CSG-Tree Pydantic schema.

No agents, no Ollama, no RAG — pure schema validation.
These tests run in milliseconds.
"""

import pytest
from pydantic import ValidationError
from src.graph.csg_tree import (
    Blueprint, CSGBox, CSGCylinder, CSGCut, CSGUnion,
    CSGFillet, CSGShell, Position,
)


class TestPrimitives:

    def test_box_valid(self):
        box = CSGBox(x=30, y=20, z=10)
        assert box.type == "box"
        assert box.x == 30

    def test_box_requires_positive_dimensions(self):
        with pytest.raises(ValidationError):
            CSGBox(x=-5, y=20, z=10)

    def test_cylinder_valid(self):
        cyl = CSGCylinder(radius=5.0, height=10.0)
        assert cyl.type == "cylinder"

    def test_position_defaults_to_origin(self):
        box = CSGBox(x=10, y=10, z=10)
        assert box.position.x == 0
        assert box.position.y == 0
        assert box.position.z == 0

    def test_position_can_be_set(self):
        box = CSGBox(x=10, y=10, z=10, position=Position(x=5, y=-3, z=0))
        assert box.position.x == 5


class TestOperations:

    def test_cut_with_two_primitives(self):
        cut = CSGCut(
            target=CSGBox(x=50, y=50, z=8),
            tool=CSGCylinder(radius=5, height=10),
        )
        assert cut.type == "cut"
        assert cut.target.type == "box"
        assert cut.tool.type == "cylinder"

    def test_union_valid(self):
        union = CSGUnion(
            target=CSGBox(x=40, y=10, z=5),
            tool=CSGBox(x=10, y=40, z=5),
        )
        assert union.type == "union"

    def test_fillet_wraps_child(self):
        fillet = CSGFillet(
            radius=2.0,
            edges=">Z",
            child=CSGBox(x=30, y=30, z=10),
        )
        assert fillet.type == "fillet"
        assert fillet.child.type == "box"

    def test_shell_valid(self):
        shell = CSGShell(
            thickness=2.0,
            open_face=">Z",
            child=CSGBox(x=60, y=40, z=30),
        )
        assert shell.type == "shell"


class TestBlueprint:

    def _simple_blueprint_dict(self):
        return {
            "description": "30mm cube",
            "root": {"type": "box", "x": 30, "y": 30, "z": 30},
        }

    def test_valid_blueprint(self):
        bp = Blueprint.model_validate(self._simple_blueprint_dict())
        assert bp.description == "30mm cube"
        assert bp.root.type == "box"

    def test_blueprint_round_trip(self):
        """to_dict() → from_dict() must produce identical object."""
        bp = Blueprint.model_validate(self._simple_blueprint_dict())
        restored = Blueprint.from_dict(bp.to_dict())
        assert restored.description == bp.description
        assert restored.root.type == bp.root.type

    def test_blueprint_with_nested_cut(self):
        data = {
            "description": "Plate with hole",
            "root": {
                "type": "cut",
                "target": {"type": "box", "x": 50, "y": 50, "z": 8},
                "tool": {"type": "cylinder", "radius": 5, "height": 10},
            }
        }
        bp = Blueprint.model_validate(data)
        assert bp.root.type == "cut"
        assert bp.root.target.type == "box"
        assert bp.root.tool.type == "cylinder"

    def test_invalid_root_type_raises(self):
        with pytest.raises(ValidationError):
            Blueprint.model_validate({
                "description": "test",
                "root": {"type": "trapezoid", "x": 10},  # not a valid type
            })

    def test_missing_description_raises(self):
        with pytest.raises(ValidationError):
            Blueprint.model_validate({
                "root": {"type": "box", "x": 30, "y": 30, "z": 30},
            })

    def test_notes_defaults_to_empty_string(self):
        bp = Blueprint.model_validate(self._simple_blueprint_dict())
        assert bp.notes == ""

    def test_deeply_nested_tree(self):
        """Four nested cuts (four holes) must validate correctly."""
        hole = lambda x, y: {
            "type": "cylinder", "radius": 1.6, "height": 6,
            "position": {"x": x, "y": y, "z": 0}
        }
        data = {
            "description": "Plate with 4 holes",
            "root": {
                "type": "cut",
                "target": {
                    "type": "cut",
                    "target": {
                        "type": "cut",
                        "target": {
                            "type": "cut",
                            "target": {"type": "box", "x": 80, "y": 60, "z": 4},
                            "tool": hole(-32, -22),
                        },
                        "tool": hole(32, -22),
                    },
                    "tool": hole(-32, 22),
                },
                "tool": hole(32, 22),
            }
        }
        bp = Blueprint.model_validate(data)
        # Walk to the deepest target
        node = bp.root
        for _ in range(4):
            if hasattr(node, "target"):
                node = node.target
        assert node.type == "box"
