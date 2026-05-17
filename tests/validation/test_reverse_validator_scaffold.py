from pathlib import Path

from src.validation import (
    BLOCKING_ENABLED,
    GRAPH_INTEGRATION_ENABLED,
    ReverseValidator,
)
from src.validation.fact_extraction import extract_facts_from_state

FEATURE_TREE_BOX = {
    "description": "Box 50x40x20",
    "build_order": ["base"],
    "features": {
        "base": {
            "type": "box",
            "params": {"x": 50.0, "y": 40.0, "z": 20.0},
            "parent": None,
            "operation": "add",
        }
    },
}


def test_reverse_validator_is_dormant_and_non_blocking():
    state = {
        "blueprint": FEATURE_TREE_BOX,
        "geometry_state": {
            "total_width": 50.0,
            "total_depth": 40.0,
            "total_height": 20.0,
            "volume": 40000.0,
        },
    }

    report = ReverseValidator().run(state)

    assert GRAPH_INTEGRATION_ENABLED is False
    assert BLOCKING_ENABLED is False
    assert report.graph_integrated is False
    assert report.blocking_enabled is False
    assert report.would_block_if_enabled is False
    assert report.has_failures is False


def test_feature_tree_facts_are_extracted_without_reading_raw_text():
    state = {
        "specification": "Dieser Text sagt absichtlich etwas anderes.",
        "blueprint": FEATURE_TREE_BOX,
        "geometry_state": {},
    }

    facts = extract_facts_from_state(state)

    assert facts.blueprint_format == "feature_tree"
    assert facts.build_order == ("base",)
    assert facts.features["base"].feature_type == "box"
    assert facts.features["base"].params["x"] == 50.0


def test_build_order_mismatch_is_a_hard_failure_but_still_non_blocking():
    broken = {
        **FEATURE_TREE_BOX,
        "build_order": ["base", "missing_hole"],
    }

    report = ReverseValidator().run({"blueprint": broken})

    assert report.has_failures is True
    assert report.would_block_if_enabled is True
    assert report.blocking_enabled is False
    assert any(
        check.check_id == "feature_count.structure" and check.status == "failed"
        for check in report.checks
    )


def test_bbox_and_volume_pass_for_simple_root_box():
    report = ReverseValidator().run(
        {
            "blueprint": FEATURE_TREE_BOX,
            "geometry_state": {
                "total_width": 50.0,
                "total_depth": 40.0,
                "total_height": 20.0,
                "volume": 40000.0,
            },
        }
    )

    statuses = {check.check_id: check.status for check in report.checks}

    assert statuses["geometry.bbox"] == "passed"
    assert statuses["geometry.volume"] == "passed"


def test_subtractive_feature_volume_is_unknown_not_passed():
    blueprint = {
        "description": "Box with hole",
        "build_order": ["base", "hole_1"],
        "features": {
            "base": {
                "type": "box",
                "params": {"x": 50.0, "y": 40.0, "z": 20.0},
                "parent": None,
                "operation": "add",
            },
            "hole_1": {
                "type": "hole_single",
                "params": {"diameter": 8.0, "depth": 20.0},
                "parent": "base",
                "operation": "subtract",
                "placement": {"face": ">Z", "position": "center"},
            },
        },
    }

    report = ReverseValidator().run(
        {
            "blueprint": blueprint,
            "geometry_state": {
                "total_width": 50.0,
                "total_depth": 40.0,
                "total_height": 20.0,
                "volume": 39000.0,
            },
        }
    )

    volume = next(check for check in report.checks if check.check_id == "geometry.volume")
    hole = next(check for check in report.checks if check.check_id == "feature_family.hole")

    assert volume.status == "unknown"
    assert hole.status == "unknown"


def test_reverse_validator_is_not_wired_into_pipeline_graph():
    pipeline_text = Path("src/graph/pipeline.py").read_text(encoding="utf-8")
    edges_text = Path("src/graph/edges.py").read_text(encoding="utf-8")

    assert "ReverseValidator" not in pipeline_text
    assert "reverse_validator" not in pipeline_text
    assert "ReverseValidator" not in edges_text
    assert "reverse_validator" not in edges_text
