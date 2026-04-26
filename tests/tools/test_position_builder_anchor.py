"""Tests for position_builder anchor + pre_rotation extraction."""

from src.tools.position_builder import build_position


def _base(**overrides) -> dict:
    base = {
        "parent": "wuerfel",
        "seite": "links",
        "ausrichtung": "zentriert",
        "orientierung": "standard",
        "anliegende_flaeche": "keine",
        "abstand": {},
        "winkel": 0,
        "anker": "",
        "pre_rotation": {},
        "notes": "",
    }
    base.update(overrides)
    return base


def test_no_anchor_fields_produces_no_anchor_key():
    pos = build_position(_base())
    assert "anchor" not in pos


def test_anker_string_builds_child_and_parent_point():
    pos = build_position(_base(anker="top_left_auf_left_edge"))
    assert pos["anchor"]["child_point"] == "top_left"
    assert pos["anchor"]["parent_point"] == "left_edge"


def test_pre_rotation_alone_creates_center_anchor():
    pos = build_position(_base(pre_rotation={"z": -10}))
    assert pos["anchor"]["child_point"] == "center"
    assert pos["anchor"]["parent_point"] == "center"
    assert pos["anchor"]["pre_rotation"] == {"z": -10.0}


def test_anchor_consumes_versatz_into_offset():
    pos = build_position(_base(
        anker="top_left_auf_left_edge",
        abstand={"versatz_unten": 10},
    ))
    assert pos["anchor"]["offset"] == {"down": 10.0}
    # center_offset must not also be emitted — would double-apply
    assert "center_offset" not in pos


def test_invalid_anchor_points_fall_back_to_center():
    pos = build_position(_base(anker="bogus_auf_nonsense"))
    assert pos["anchor"]["child_point"] == "center"
    assert pos["anchor"]["parent_point"] == "center"


def test_pre_rotation_zero_values_ignored():
    pos = build_position(_base(pre_rotation={"x": 0, "y": 0, "z": 0}))
    assert "anchor" not in pos


def test_anchor_consumes_abstand_oben_as_offset_down():
    # Run 4e2fd4ab: user said "10mm von oben nach unten versetzt" — LLM wrote
    # it as abstand_oben=10, builder must translate to offset.down=10.
    pos = build_position(_base(
        anker="top_left_auf_left_edge",
        abstand={"abstand_oben": 10},
    ))
    assert pos["anchor"]["offset"] == {"down": 10.0}


def test_anchor_versatz_takes_precedence_over_abstand():
    # Both specified → versatz_* (explicit center-shift) wins, not stacked.
    pos = build_position(_base(
        anker="top_left_auf_left_edge",
        abstand={"versatz_unten": 5, "abstand_oben": 10},
    ))
    assert pos["anchor"]["offset"] == {"down": 5.0}
