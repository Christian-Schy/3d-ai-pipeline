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


# ── Check 11: Slot-Restwandstaerke (Mittellinien-Konvention) ────────────────

def test_slot_with_enough_restwand_emits_no_warning():
    # Slot length 40 entlang Y (angle 90), centre offset_y=10 → spans y∈[-10,30].
    # Face half_y = 50 → top clearance = 50-10-20 = 20mm. Reichlich.
    slot = _slot("nut_safe", offset_x=0, offset_y=10)
    issues = run_coordinate_check(_bp(slot))
    assert not [i for i in issues if i.check == "slot_restwandstaerke"]


def test_slot_tight_to_edge_emits_restwand_warning():
    # offset_y=25 → spans y∈[5, 45]. Top clearance = 50-25-20 = 5 ✓.
    # offset_y=29.8 → spans y∈[9.8, 49.8]. Top clearance = 0.2 < 0.5 → WARNING.
    slot = _slot("nut_tight", offset_x=0, offset_y=29.8)
    issues = run_coordinate_check(_bp(slot))
    warns = [i for i in issues if i.check == "slot_restwandstaerke"]
    assert warns, f"expected slot_restwandstaerke warning, got: {issues}"
    assert warns[0].severity == "WARNING"
    assert "oberer" in warns[0].message.lower()


def test_slot_overhang_emits_negative_restwand_warning():
    # offset_y=35 → spans y∈[15, 55]. Top end 55 > 50 → clearance -5 (overhang).
    slot = _slot("nut_overhang", offset_x=0, offset_y=35)
    issues = run_coordinate_check(_bp(slot))
    warns = [i for i in issues if i.check == "slot_restwandstaerke"]
    assert warns
    # Klare Ueberhang-Meldung (negativer Wert in der Message).
    assert "-5" in warns[0].message or "-4.9" in warns[0].message


def test_slot_rotated_45_uses_aabb_aware_clearance():
    # Slot length 40, width 5, angle 45° auf 100er Face.
    # AABB-Halbachsen: (40/2)*cos45 + (5/2)*sin45 = ~14.14+1.77 = ~15.9
    # Bei offset (0, 30): top clearance = 50-30-15.9 = 4.1 mm > 0.5 → kein WARN.
    # Bei offset (0, 35): top clearance = 50-35-15.9 = -0.9 < 0.5 → WARN.
    safe = _slot("nut_45_safe", offset_x=0, offset_y=30)
    safe["placement"]["angle_deg"] = 45.0
    tight = _slot("nut_45_tight", offset_x=0, offset_y=35)
    tight["placement"]["angle_deg"] = 45.0

    safe_issues = run_coordinate_check(_bp(safe))
    tight_issues = run_coordinate_check(_bp(tight))

    assert not [i for i in safe_issues if i.check == "slot_restwandstaerke"]
    assert [i for i in tight_issues if i.check == "slot_restwandstaerke"]


# ── Rotation-aware AABB fuer Tasche/Pocket (statt axis-aligned x/2,y/2) ──

def _pocket(fid: str, x: float, y: float,
            offset_x: float = 0.0, offset_y: float = 0.0,
            angle_deg: float = 0.0) -> dict:
    return {
        "id": fid,
        "type": "pocket_rect",
        "params": {"x": x, "y": y, "depth": 5},
        "parent": "wuerfel",
        "operation": "subtract",
        "placement": {
            "face": ">Z",
            "alignment": "centered",
            "offset_x": offset_x,
            "offset_y": offset_y,
            "angle_deg": angle_deg,
            "notes": "",
        },
    }


def test_rotated_pocket_overhang_now_detected():
    # 60x40 Tasche um 30° gedreht bei offset_x=20, 100er Wuerfel.
    # Axis-aligned: x_half=30 → 20+30=50 → kein Ueberhang (falsch).
    # Rotated AABB: x_half = 30*cos30 + 20*sin30 = 35.98
    #               → 20 + 35.98 = 55.98 > 50 → ~6mm Ueberhang.
    pocket = _pocket("tasche_rot", x=60, y=40, offset_x=20, angle_deg=30)
    issues = run_coordinate_check(_bp(pocket))
    overhang = [i for i in issues if i.check == "offset_overhang_x"]
    assert overhang, (
        f"rotierte Tasche sollte Ueberhang melden; got: {issues}"
    )


def test_rotated_pocket_safely_inside_no_overhang():
    # 30x20 Tasche um 45° gedreht bei offset (10, 10).
    # Rotated AABB: x_half = y_half = 15*0.707 + 10*0.707 = 17.68.
    # Right reach = 10 + 17.68 = 27.68 → safe.
    pocket = _pocket("tasche_safe", x=30, y=20, offset_x=10, offset_y=10, angle_deg=45)
    issues = run_coordinate_check(_bp(pocket))
    assert not [i for i in issues if i.check.startswith("offset_overhang")]
    assert not [i for i in issues if i.check.startswith("offset_bounds")]


def test_unrotated_pocket_behavior_unchanged():
    # Sanity: angle=0 muss exakt wie vorher rechnen.
    # 50x30 Tasche bei offset (10, 0): x_half=25 → 10+25=35 < 50. Safe.
    pocket = _pocket("tasche_axis_aligned", x=50, y=30, offset_x=10, angle_deg=0)
    issues = run_coordinate_check(_bp(pocket))
    assert not [i for i in issues if i.check.startswith("offset_overhang")]


def test_rotated_pocket_90deg_swaps_aabb_axes():
    # 80x20 Tasche um 90° gedreht — AABB-Achsen werden getauscht:
    # x_half wird zu y/2=10, y_half zu x/2=40.
    # Bei offset_y=15 mit y_half=40 → 15+40=55 > 50 → Ueberhang Y.
    pocket = _pocket("tasche_90", x=80, y=20, offset_y=15, angle_deg=90)
    issues = run_coordinate_check(_bp(pocket))
    assert [i for i in issues if i.check == "offset_overhang_y"]
