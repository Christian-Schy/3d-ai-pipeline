"""Tests for scripts.run_real_goldens blueprint pairing."""

from scripts.run_real_goldens import compare_blueprints


def _bp(features: dict) -> dict:
    root = {
        "wuerfel": {
            "type": "box",
            "params": {"x": 100, "y": 100, "z": 100},
            "parent": None,
        }
    }
    root.update(features)
    return {"features": root}


def _slot(length: int, angle: float) -> dict:
    return {
        "type": "slot",
        "parent": "wuerfel",
        "params": {"length": length, "width": 5, "depth": 5},
        "placement": {
            "face": ">Z",
            "alignment": "centered",
            "offset_x": 0.0,
            "offset_y": 0.0,
            "angle_deg": angle,
        },
    }


def test_pairing_uses_angle_and_params_when_offsets_tie():
    expected = _bp({
        "expected_centered_y": _slot(40, 90),
        "expected_rotated_x": _slot(50, 15),
    })
    got = _bp({
        "got_rotated_x": _slot(50, 15),
        "got_centered_y": _slot(40, 90),
    })

    assert compare_blueprints(got, expected) == []
