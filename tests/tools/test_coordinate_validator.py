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


def test_slot_offset_bounds_use_length_axis_at_angle_zero():
    # angle=0 means Slot-Laenge liegt auf face-X. The generic offset-bounds
    # check must therefore use length/2 on X, not width/2.
    slot = _slot("nut_x_edge", offset_x=35, offset_y=0)
    slot["placement"]["angle_deg"] = 0.0
    issues = run_coordinate_check(_bp(slot))
    assert [i for i in issues if i.check == "offset_overhang_x"]


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


# ── Check 12: Pattern-Kind-Bohrungen gegen Bauteilrand ─────────────────────

def _pattern(fid: str, ftype: str, params: dict,
             offset_x: float = 0.0, offset_y: float = 0.0,
             angle_deg: float = 0.0) -> dict:
    return {
        "id": fid,
        "type": ftype,
        "params": params,
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


def test_grid_pattern_inside_no_warning():
    # 3x3 Raster, spacing 20, Durchmesser 5, zentriert auf 100er-Wuerfel.
    # Aeusserste Bohrungen bei ±20, +/-2.5 → 22.5 < 50. Klar drin.
    pat = _pattern("grid_safe", "hole_pattern_grid",
                   {"rows": 3, "cols": 3, "spacing_x": 20, "spacing_y": 20,
                    "hole_diameter": 5})
    issues = run_coordinate_check(_bp(pat))
    assert not [i for i in issues if i.check == "pattern_child_bounds"]


def test_grid_pattern_offset_overhang_warns_per_child():
    # 3x3 Raster spacing 20 bei offset_x=30. Aeusserste rechts bei +30+20=+50.
    # Mit Durchmesser 10 (radius 5) → +50+5=+55 > 50 → Ueberhang 5mm.
    # 3 Kinder in der rechten Spalte ragen raus (Mitte+oben+unten).
    pat = _pattern("grid_edge", "hole_pattern_grid",
                   {"rows": 3, "cols": 3, "spacing_x": 20, "spacing_y": 20,
                    "hole_diameter": 10},
                   offset_x=30)
    issues = run_coordinate_check(_bp(pat))
    warns = [i for i in issues if i.check == "pattern_child_bounds"]
    assert len(warns) == 3, f"expected 3 warnings (rechte Spalte), got {len(warns)}"
    assert all("X" in w.message for w in warns)


def test_circular_pattern_fits_no_warning():
    # Lochkreis 6 Bohrungen Ø5 auf Teilkreis 40mm, zentriert.
    # Aeusserster Punkt: 20+2.5 = 22.5 < 50.
    pat = _pattern("circ_safe", "hole_pattern_circular",
                   {"count": 6, "bolt_circle_diameter": 40, "hole_diameter": 5})
    issues = run_coordinate_check(_bp(pat))
    assert not [i for i in issues if i.check == "pattern_child_bounds"]


def test_circular_pattern_too_big_warns_for_all_holes():
    # Lochkreis 4 Bohrungen Ø10 auf Teilkreis 95mm bei offset (0, 0).
    # Aeusserster Punkt: 47.5+5 = 52.5 > 50 → 2.5mm Ueberhang.
    # Alle 4 Kinder ragen raus (eines pro Seite).
    pat = _pattern("circ_big", "hole_pattern_circular",
                   {"count": 4, "bolt_circle_diameter": 95, "hole_diameter": 10})
    issues = run_coordinate_check(_bp(pat))
    warns = [i for i in issues if i.check == "pattern_child_bounds"]
    assert len(warns) == 4


def test_linear_pattern_x_at_edge_warns_for_outermost():
    # 4 Bohrungen Ø6 entlang X, spacing 20, offset_x=20.
    # Positionen: -10, +10, +30, +50 (relativ Pattern-Mitte −30 bis +30 + 20).
    # Aeusserste rechts: +50+3=+53 > 50 → 3mm Ueberhang. NUR die rechte.
    pat = _pattern("lin_edge", "hole_pattern_linear",
                   {"count": 4, "spacing": 20, "direction": "x", "hole_diameter": 6},
                   offset_x=20)
    issues = run_coordinate_check(_bp(pat))
    warns = [i for i in issues if i.check == "pattern_child_bounds"]
    assert len(warns) == 1
    assert "X" in warns[0].message


def test_grid_pattern_rotation_applies_to_child_positions():
    # 2x2 Raster spacing 30, Durchmesser 5, um 45° gedreht, zentriert.
    # Ohne Rotation: Ecken bei ±15. Mit Rot 45°: Diagonalen-Halbachse =
    # sqrt(15² + 15²) ≈ 21.2 → +/-21.2 in X UND Y. +21.2+2.5=23.7 < 50: safe.
    # Aber bei Spacing 60: Ecken bei ±30 → Rot 45° → ±42.4 → 42.4+2.5=44.9 <
    # 50, safe. Bei spacing 70: Ecken bei ±35 → Rot 45° → ±49.5 → 49.5+2.5=52
    # > 50 → Ueberhang.
    pat_safe = _pattern("grid_rot_safe", "hole_pattern_grid",
                        {"rows": 2, "cols": 2, "spacing_x": 30, "spacing_y": 30,
                         "hole_diameter": 5},
                        angle_deg=45)
    pat_overhang = _pattern("grid_rot_oh", "hole_pattern_grid",
                            {"rows": 2, "cols": 2, "spacing_x": 70,
                             "spacing_y": 70, "hole_diameter": 5},
                            angle_deg=45)
    safe_issues = run_coordinate_check(_bp(pat_safe))
    oh_issues = run_coordinate_check(_bp(pat_overhang))
    assert not [i for i in safe_issues if i.check == "pattern_child_bounds"]
    oh_warns = [i for i in oh_issues if i.check == "pattern_child_bounds"]
    assert len(oh_warns) >= 1, f"expected at least 1 rotation-overhang, got {oh_warns}"


def test_pattern_many_overhangs_aggregates():
    # Grid 4x4 spacing 30 bei offset (0,0). Sehr viele Ueberhaenge erwartet.
    # Aeusserste Position: ±45 ± 2.5 (diameter 5) → +47.5 < 50 safe.
    # Mit diameter 8: +45+4 = +49 < 50 safe. Bei spacing 32 → +48+2.5 > 50.
    pat = _pattern("grid_many_oh", "hole_pattern_grid",
                   {"rows": 4, "cols": 4, "spacing_x": 32, "spacing_y": 32,
                    "hole_diameter": 5})
    issues = run_coordinate_check(_bp(pat))
    warns = [i for i in issues if i.check == "pattern_child_bounds"]
    # Max 5 individual warnings, plus optional aggregate.
    assert 1 <= len(warns) <= 6


def test_circular_pattern_canonical_schema_triggers_bolt_circle_check():
    # Canonical pipeline params are bolt_circle_diameter + hole_diameter.
    # This should not silently skip Check 4.
    pat = _pattern("circ_too_wide", "hole_pattern_circular",
                   {"count": 4, "bolt_circle_diameter": 100, "hole_diameter": 10})
    issues = run_coordinate_check(_bp(pat))
    assert [i for i in issues if i.check == "bolt_circle_fits"]
