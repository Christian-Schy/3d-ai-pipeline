"""Tests for coordinate_validator edge-cut bounds."""

from src.tools.coordinate_validator import run_coordinate_check


def _bp(feature: dict) -> dict:
    return {
        "build_order": ["wuerfel", feature["id"]],
        "features": {
            "wuerfel": {
                "id": "wuerfel",
                "type": "box",
                "params": {"x": 100, "y": 100, "z": 100},
                "parent": None,
                "operation": "add",
            },
            feature["id"]: feature,
        },
    }


def _slot(fid: str, offset_x: float, offset_y: float = 0.0) -> dict:
    return {
        "id": fid,
        "type": "slot",
        "params": {"width": 5, "depth": 5, "length": 40},
        "parent": "wuerfel",
        "operation": "subtract",
        "placement": {
            "face": ">Z",
            "alignment": "centered",
            "offset_x": offset_x,
            "offset_y": offset_y,
            "angle_deg": 90.0,
            "notes": "",
        },
    }


def test_subtractive_edge_slot_overhang_is_warning_not_error():
    issues = run_coordinate_check(_bp(_slot("nut_edge", offset_x=50)))

    assert not [i for i in issues if i.severity == "ERROR"]
    assert any(i.check == "offset_overhang_x" for i in issues)


def test_subtractive_slot_fully_outside_is_error():
    issues = run_coordinate_check(_bp(_slot("nut_outside", offset_x=80)))

    assert any(i.severity == "ERROR" and i.check == "offset_bounds_x" for i in issues)


def test_feature_in_pocket_partial_overhang_is_warning_not_error():
    pocket = {
        "id": "tasche",
        "type": "pocket_rect",
        "params": {"x": 60, "y": 40, "depth": 10},
        "parent": "wuerfel",
        "operation": "subtract",
        "placement": {
            "face": ">Z",
            "alignment": "centered",
            "offset_x": 0,
            "offset_y": 0,
            "angle_deg": 0,
        },
    }
    hole = {
        "id": "hole_in_tasche",
        "type": "hole_single",
        "params": {"diameter": 8, "depth": 15},
        "parent": "tasche",
        "operation": "subtract",
        "placement": {
            "face": ">Z",
            "alignment": "centered",
            "offset_x": 25,
            "offset_y": 17,
            "angle_deg": 0,
            "feature_parent": "tasche",
        },
    }
    bp = _bp(pocket)
    bp["build_order"].append(hole["id"])
    bp["features"][hole["id"]] = hole

    issues = run_coordinate_check(bp)

    assert not [i for i in issues if i.severity == "ERROR"]
    assert any(i.check == "inside_pocket_overhang_y" for i in issues)


def test_feature_in_pocket_fully_outside_is_error():
    pocket = {
        "id": "tasche",
        "type": "pocket_rect",
        "params": {"x": 60, "y": 40, "depth": 10},
        "parent": "wuerfel",
        "operation": "subtract",
        "placement": {"face": ">Z", "offset_x": 0, "offset_y": 0, "angle_deg": 0},
    }
    hole = {
        "id": "hole_outside_tasche",
        "type": "hole_single",
        "params": {"diameter": 8, "depth": 15},
        "parent": "tasche",
        "operation": "subtract",
        "placement": {
            "face": ">Z",
            "offset_x": 0,
            "offset_y": 30,
            "angle_deg": 0,
            "feature_parent": "tasche",
        },
    }
    bp = _bp(pocket)
    bp["build_order"].append(hole["id"])
    bp["features"][hole["id"]] = hole

    issues = run_coordinate_check(bp)

    assert any(i.severity == "ERROR" and i.check == "inside_pocket_y" for i in issues)
