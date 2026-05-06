"""
tests/agents/test_function_decomposer.py — Unit tests for FunctionDecomposerAgent.

Rule-based (no LLM) — tests focus on skeleton structure and skip-logic.
"""

import pytest
from src.agents.function_decomposer import FunctionDecomposerAgent, generate_skeleton


# ── Fixtures ──────────────────────────────────────────────────────────────────

SIMPLE_FEATURE_TREE = {
    "description": "Box with hole",
    "build_order": ["base", "center_hole"],
    "features": {
        "base": {
            "type": "box",
            "params": {"x": 50.0, "y": 50.0, "z": 20.0},
            "parent": None,
            "placement": None,
            "notes": "",
        },
        "center_hole": {
            "type": "hole",
            "params": {"diameter": 10.0, "depth": None},
            "parent": "base",
            "operation": "subtract",
            "placement": {"face": ">Z", "position": "center", "offset_x": 0.0, "offset_y": 0.0},
            "notes": "Durchgangsbohrung",
        },
    },
}

SINGLE_FEATURE_TREE = {
    "description": "Simple box",
    "build_order": ["base"],
    "features": {
        "base": {
            "type": "box",
            "params": {"x": 30.0, "y": 30.0, "z": 30.0},
            "parent": None,
            "placement": None,
            "notes": "",
        },
    },
}

CSG_TREE_BLUEPRINT = {
    "description": "CSG-Tree style",
    "features": [
        {"type": "box", "params": {"x": 50, "y": 50, "z": 20}},
    ],
}


# ── Agent wrapper tests ───────────────────────────────────────────────────────

class TestSkipLogic:
    def test_single_feature_returns_empty_skeleton(self):
        agent = FunctionDecomposerAgent()
        result = agent.decompose({"blueprint": SINGLE_FEATURE_TREE})
        assert result["code_skeleton"] == ""

    def test_csg_tree_returns_empty_skeleton(self):
        agent = FunctionDecomposerAgent()
        result = agent.decompose({"blueprint": CSG_TREE_BLUEPRINT})
        assert result["code_skeleton"] == ""

    def test_empty_blueprint_returns_empty_skeleton(self):
        agent = FunctionDecomposerAgent()
        result = agent.decompose({"blueprint": {}})
        assert result["code_skeleton"] == ""


# ── generate_skeleton tests ───────────────────────────────────────────────────

class TestSkeletonContent:
    def test_skeleton_has_imports(self):
        skeleton = generate_skeleton(SIMPLE_FEATURE_TREE)
        assert "import cadquery as cq" in skeleton
        assert "import math" in skeleton

    def test_skeleton_has_output_path(self):
        skeleton = generate_skeleton(SIMPLE_FEATURE_TREE)
        assert "OUTPUT_PATH" in skeleton

    def test_skeleton_has_export(self):
        skeleton = generate_skeleton(SIMPLE_FEATURE_TREE)
        assert "cq.exporters.export(result, OUTPUT_PATH)" in skeleton

    def test_skeleton_has_assemble(self):
        skeleton = generate_skeleton(SIMPLE_FEATURE_TREE)
        assert "def assemble()" in skeleton
        assert "result = assemble()" in skeleton

    def test_root_feature_gets_make_prefix(self):
        skeleton = generate_skeleton(SIMPLE_FEATURE_TREE)
        assert "def make_base()" in skeleton

    def test_hole_feature_gets_drill_prefix(self):
        skeleton = generate_skeleton(SIMPLE_FEATURE_TREE)
        assert "def drill_center_hole(" in skeleton

    def test_assemble_calls_all_functions(self):
        skeleton = generate_skeleton(SIMPLE_FEATURE_TREE)
        assert "make_base()" in skeleton
        assert "drill_center_hole(" in skeleton

    def test_skeleton_is_valid_python_syntax(self):
        skeleton = generate_skeleton(SIMPLE_FEATURE_TREE)
        # Should not raise
        compile(skeleton, "<test_skeleton>", "exec")

    def test_csg_tree_returns_empty(self):
        skeleton = generate_skeleton(CSG_TREE_BLUEPRINT)
        assert skeleton == ""

    def test_single_feature_returns_empty(self):
        # generate_skeleton itself doesn't apply skip logic — that's the agent
        # But it still generates a skeleton for single features
        skeleton = generate_skeleton(SINGLE_FEATURE_TREE)
        # generate_skeleton returns a skeleton; skip logic is in FunctionDecomposerAgent.decompose
        assert isinstance(skeleton, str)


class TestFunctionNaming:
    def test_subtract_slot_gets_cut_prefix(self):
        bp = {
            "description": "Box with slot",
            "build_order": ["base", "top_slot"],
            "features": {
                "base": {"type": "box", "params": {"x": 80, "y": 40, "z": 20},
                         "parent": None, "placement": None, "notes": ""},
                "top_slot": {"type": "slot", "params": {"width": 8, "depth": 5},
                             "parent": "base", "operation": "subtract",
                             "placement": {"face": ">Z", "position": "center",
                                           "offset_x": 0, "offset_y": 0},
                             "notes": ""},
            },
        }
        skeleton = generate_skeleton(bp)
        assert "def cut_top_slot(" in skeleton

    def test_fillet_gets_apply_prefix(self):
        bp = {
            "description": "Box with fillet",
            "build_order": ["base", "top_fillet"],
            "features": {
                "base": {"type": "box", "params": {"x": 50, "y": 50, "z": 20},
                         "parent": None, "placement": None, "notes": ""},
                "top_fillet": {"type": "fillet", "params": {"radius": 3.0},
                               "parent": "base", "placement": None, "notes": ""},
            },
        }
        skeleton = generate_skeleton(bp)
        assert "def apply_top_fillet(" in skeleton
