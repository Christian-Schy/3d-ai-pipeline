"""
tests/tools/test_geometry_precheck_feature_tree.py — Tests for Feature Tree support in geometry_precheck.

Regression tests for the bug: 'str' object has no attribute 'get'
which occurred when blueprint["features"] was a dict (Feature Tree)
and code tried to iterate its string keys as feature objects.
"""

import pytest
from src.tools.geometry_precheck import (
    run_geometry_precheck,
    check_feature_count,
    check_depth_consistency,
)


# ── Feature Tree fixtures ─────────────────────────────────────────────────────

FEATURE_TREE_BOX_HOLE = {
    "description": "Box 50x50x30mm with hole ∅10mm",
    "build_order": ["base", "center_hole"],
    "features": {
        "base": {
            "type": "box",
            "params": {"x": 50.0, "y": 50.0, "z": 30.0},
            "parent": None,
            "placement": None,
            "notes": "",
        },
        "center_hole": {
            "type": "hole",
            "params": {"diameter": 10.0, "depth": None},
            "parent": "base",
            "placement": {"face": ">Z", "position": "center", "offset_x": 0.0, "offset_y": 0.0},
            "notes": "",
        },
    },
}

FEATURE_TREE_SIMPLE = {
    "description": "Simple 30mm cube",
    "build_order": ["base_cube"],
    "features": {
        "base_cube": {
            "type": "box",
            "params": {"x": 30.0, "y": 30.0, "z": 30.0},
            "parent": None,
            "placement": None,
            "notes": "",
        },
    },
}

FEATURE_TREE_WITH_PATTERN = {
    "description": "Plate with bolt circle",
    "build_order": ["base", "bolt_circle"],
    "features": {
        "base": {
            "type": "cylinder",
            "params": {"diameter": 100.0, "height": 10.0},
            "parent": None,
            "placement": None,
            "notes": "",
        },
        "bolt_circle": {
            "type": "hole_pattern_circular",
            "params": {"circle_diameter": 70.0, "n_holes": 4, "diameter": 8.0, "depth": None},
            "parent": "base",
            "placement": {"face": ">Z", "position": "center", "offset_x": 0.0, "offset_y": 0.0},
            "notes": "",
        },
    },
}


# ── Regression: no crash on Feature Tree ─────────────────────────────────────

class TestNoStrGetCrash:
    """Regression tests for 'str' object has no attribute 'get' bug."""

    def test_run_precheck_does_not_crash(self):
        """run_geometry_precheck must not raise AttributeError on Feature Tree."""
        try:
            result = run_geometry_precheck(
                blueprint=FEATURE_TREE_BOX_HOLE,
                specification="Box 50x50x30 with hole 10mm",
                volume_actual=75000.0,
                is_watertight=True,
                bbox_dims=(50.0, 50.0, 30.0),
            )
            # Returns a GeometryReport object
            assert result is not None
        except AttributeError as e:
            pytest.fail(f"AttributeError crash on Feature Tree: {e}")

    def test_check_feature_count_does_not_crash(self):
        """check_feature_count must handle dict-format features."""
        try:
            result = check_feature_count("Box with hole", FEATURE_TREE_BOX_HOLE)
            assert isinstance(result, list)
        except AttributeError as e:
            pytest.fail(f"AttributeError crash on Feature Tree: {e}")

    def test_check_depth_consistency_does_not_crash(self):
        """check_depth_consistency must handle dict-format features."""
        try:
            result = check_depth_consistency("Box with hole", FEATURE_TREE_BOX_HOLE)
            assert isinstance(result, list)
        except AttributeError as e:
            pytest.fail(f"AttributeError crash on Feature Tree: {e}")

    def test_single_feature_tree_no_crash(self):
        try:
            result = run_geometry_precheck(
                blueprint=FEATURE_TREE_SIMPLE,
                specification="Simple 30mm cube",
                volume_actual=27000.0,
                is_watertight=True,
                bbox_dims=(30.0, 30.0, 30.0),
            )
            assert result is not None
        except AttributeError as e:
            pytest.fail(f"AttributeError crash on single-feature Feature Tree: {e}")

    def test_pattern_feature_tree_no_crash(self):
        try:
            result = run_geometry_precheck(
                blueprint=FEATURE_TREE_WITH_PATTERN,
                specification="Round plate with 4 bolt holes",
                volume_actual=70000.0,
                is_watertight=True,
                bbox_dims=(100.0, 100.0, 10.0),
            )
            assert result is not None
        except AttributeError as e:
            pytest.fail(f"AttributeError on pattern Feature Tree: {e}")


# ── Correct feature detection ─────────────────────────────────────────────────

class TestFeatureTreeFeatureDetection:
    def test_feature_count_returns_list(self):
        result = check_feature_count("Box 50x50x30 with hole 10mm", FEATURE_TREE_BOX_HOLE)
        assert isinstance(result, list)

    def test_depth_check_returns_list(self):
        result = check_depth_consistency("Box with hole", FEATURE_TREE_BOX_HOLE)
        assert isinstance(result, list)

    def test_feature_count_not_string_key_count(self):
        """Regression: must count feature VALUES, not string dict keys."""
        # Blueprint has 2 features (base + center_hole)
        # A bug would iterate keys ("base", "center_hole" as strings) and call .get() on them
        issues = check_feature_count("Box with hole", FEATURE_TREE_BOX_HOLE)
        # Should not produce "no features found" error
        issue_messages = [i.get("message", "").lower() for i in issues]
        assert not any("no feature" in m for m in issue_messages)


# ── CSG-Tree still works ──────────────────────────────────────────────────────

class TestCsgTreeStillWorks:
    def test_csg_tree_feature_count_no_crash(self):
        csg_blueprint = {
            "description": "Box with hole",
            "features": [
                {"type": "box", "params": {"x": 50, "y": 50, "z": 30}},
                {"type": "hole", "params": {"diameter": 10, "depth": None}, "position": "center"},
            ],
        }
        try:
            result = check_feature_count("Box with hole", csg_blueprint)
            assert isinstance(result, list)
        except Exception as e:
            pytest.fail(f"CSG-Tree check_feature_count crashed: {e}")
