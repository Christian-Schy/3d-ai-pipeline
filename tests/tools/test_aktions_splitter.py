"""Tests for src/tools/aktions_splitter.py — deterministic action splitter.

Covers the basics (empty input, part-declaration stripping, nesting) and
the three reference runs cited in ADR 0003 (70d27d2f, 6efaa489, 14fa8d40).
"""
from __future__ import annotations

from src.tools.aktions_splitter import split_spec_into_aktionen


def _teile_single(name: str = "wuerfel") -> list[dict]:
    return [{"id": name, "type": "box", "raw_params": {"x": 200, "y": 200, "z": 200}}]


# ─── Basics ───────────────────────────────────────────────────────────


def test_empty_spec_returns_empty():
    assert split_spec_into_aktionen("", _teile_single()) == []


def test_empty_teile_returns_empty():
    assert split_spec_into_aktionen("oben eine Bohrung 10mm", []) == []


def test_pure_part_declaration_dropped():
    """'200mm wuerfel' alone has no side keyword → drop the segment."""
    assert split_spec_into_aktionen("200mm wuerfel", _teile_single()) == []


def test_single_action_no_nesting():
    out = split_spec_into_aktionen(
        "oben eine Bohrung 10mm zentral",
        _teile_single(),
    )
    assert len(out) == 1
    a = out[0]
    assert a["phrase"] == "oben eine Bohrung 10mm zentral"
    assert a["teil_id"] == "wuerfel"
    assert a["phrase_idx"] == 0
    assert a["parent_phrase_idx"] is None


def test_part_declaration_stripped_then_action():
    out = split_spec_into_aktionen(
        "200mm wuerfel oben eine Bohrung 10mm",
        _teile_single(),
    )
    assert len(out) == 1
    assert out[0]["phrase"] == "oben eine Bohrung 10mm"


def test_double_comma_treated_as_break():
    out = split_spec_into_aktionen(
        "oben eine Bohrung 10mm,, oben eine Tasche 20x20x5",
        _teile_single(),
    )
    assert len(out) == 2
    assert [a["phrase_idx"] for a in out] == [0, 1]


def test_trailing_comma_ignored():
    out = split_spec_into_aktionen(
        "oben eine Bohrung 10mm,",
        _teile_single(),
    )
    assert len(out) == 1


def test_adjective_form_rechten_does_not_split():
    """'rechten' (adjective) inside a phrase must not be confused with the
    bare side-keyword 'rechts'. The whole text stays one phrase."""
    out = split_spec_into_aktionen(
        "oben von der rechten seite 20mm entfernt eine Bohrung 10mm",
        _teile_single(),
    )
    assert len(out) == 1
    assert "rechten seite" in out[0]["phrase"]


# ─── Verschachtelung ──────────────────────────────────────────────────


def test_nested_in_der_tasche_creates_parent_child():
    out = split_spec_into_aktionen(
        "oben eine Tasche 60x40x10 in der Tasche eine Bohrung 8mm",
        _teile_single(),
    )
    assert len(out) == 2
    parent, child = out
    assert parent["phrase"].startswith("oben eine Tasche")
    assert parent["parent_phrase_idx"] is None
    assert parent["phrase_idx"] == 0
    assert child["phrase"].startswith("in der Tasche")
    assert child["parent_phrase_idx"] == 0
    assert child["phrase_idx"] == 1


def test_two_children_share_same_parent():
    out = split_spec_into_aktionen(
        "oben eine Tasche 60x40x10 "
        "in der Tasche eine Bohrung 8mm "
        "in der Tasche noch eine Bohrung 5mm",
        _teile_single(),
    )
    assert len(out) == 3
    assert out[0]["parent_phrase_idx"] is None
    assert out[1]["parent_phrase_idx"] == 0
    assert out[2]["parent_phrase_idx"] == 0
    assert out[2]["phrase_idx"] == 2


def test_nested_marker_innerhalb_recognized():
    out = split_spec_into_aktionen(
        "oben eine Tasche 60x40x10 innerhalb eine Bohrung 5mm",
        _teile_single(),
    )
    assert len(out) == 2
    assert out[1]["parent_phrase_idx"] == 0


def test_nested_marker_darin_recognized():
    out = split_spec_into_aktionen(
        "oben eine Tasche 60x40x10 darin eine Bohrung 5mm",
        _teile_single(),
    )
    assert len(out) == 2
    assert out[1]["parent_phrase_idx"] == 0


# ─── Multi-part Counter / Zuordnung ───────────────────────────────────


def test_phrase_idx_runs_per_teil_in_multipart():
    out = split_spec_into_aktionen(
        "wuerfel oben eine Bohrung 10mm, "
        "wuerfel oben eine Tasche 20x20x5, "
        "platte oben eine Tasche 30x30x10",
        [
            {"id": "wuerfel", "type": "box", "raw_params": {"x": 50, "y": 50, "z": 50}},
            {"id": "platte", "type": "box", "raw_params": {"x": 40, "y": 40, "z": 20}},
        ],
    )
    by_teil: dict[str, list[int]] = {}
    for a in out:
        by_teil.setdefault(a["teil_id"], []).append(a["phrase_idx"])

    assert by_teil["wuerfel"] == [0, 1]
    assert by_teil["platte"] == [0]


def test_unknown_teil_segment_falls_back_to_last_seen():
    out = split_spec_into_aktionen(
        "wuerfel oben eine Bohrung 10mm, "
        "oben eine Tasche 20x20x5",  # no teil-name → carry "wuerfel"
        [
            {"id": "wuerfel", "type": "box", "raw_params": {"x": 50, "y": 50, "z": 50}},
            {"id": "platte", "type": "box", "raw_params": {"x": 40, "y": 40, "z": 20}},
        ],
    )
    assert len(out) == 2
    assert all(a["teil_id"] == "wuerfel" for a in out)


# ─── Reference-Runs aus ADR 0003 ──────────────────────────────────────


def test_run_70d27d2f_yields_5_phrases():
    """Run 70d27d2f / 965da548: 1 Tasche+2 Bohrungen, dann 1 Tasche+1 Bohrung."""
    spec = (
        "200mm würfel oben von der rechten seite 40mm entfernt von oben 30mm entfernt eine "
        "tasche 60x40x10 um 10 grad gedreht in der tasche um 15mm nach rechts versetzt und "
        "um 10mm nach oben versetzt eine 10mm bohrung 10 tief in der tasche noch eine "
        "bohrung von der linken kante 10mm entfernt von der oberen 10mm entfernt eine 10mm "
        "bohrung 10tief, oben um 20mm nach unten und um 20mm nach links eine tasche "
        "50x40x10 versetzt um 20grad gedreht in der tasche eine bohrung oben links jeweils "
        "von den kanten entfernt um 5mm eine 8mm bohrung 10 tief"
    )
    out = split_spec_into_aktionen(spec, _teile_single())

    assert len(out) == 5
    parents = [a for a in out if a["parent_phrase_idx"] is None]
    children = [a for a in out if a["parent_phrase_idx"] is not None]
    assert len(parents) == 2
    assert len(children) == 3

    # Parent 0 (Tasche 60x40x10) has 2 children
    assert children[0]["parent_phrase_idx"] == parents[0]["phrase_idx"]
    assert children[1]["parent_phrase_idx"] == parents[0]["phrase_idx"]
    # Parent 1 (Tasche 50x40x10) has 1 child
    assert children[2]["parent_phrase_idx"] == parents[1]["phrase_idx"]


def test_run_6efaa489_three_pocket_hole_pairs():
    """Run 6efaa489: 3 Tasche+Bohrung pairs → 6 phrases (was 3 in old Step B)."""
    spec = (
        "200mm würfel, rechts eine Tasche 20x30x10 die obere Kante von oben 10mm entfernt "
        "die linke Seite von links 10mm entfernt gegen Uhrzeigersinn um 20grad rotiert in "
        "der tasche nach rechts 5mm versetzt und von der oberen kante 5mm entfernt eine "
        "8mm bohrung 10 tief, rechts eine Tasche 30x20x10 von der linken Seite 20mm "
        "entfernt die untere Seite von unten 10mm entfernt im Uhrzeigersinn um 20grad in "
        "der tasche von der oberen seite 5mm entfernt und von der rechten seite 5mm "
        "entfernt eine 8mm bohrung 10 tief, rechts eine Tasche 40x40x10 von der rechten "
        "Seite 25mm entfernt von der unteren Seite 25mm entfernt 20grad gegen Uhrzeigersinn "
        "gedreht 10mm nach rechts und 10mm nach oben versetzt sol in der tasche eine 10mm "
        "bohrung 10mm tief hin,"
    )
    out = split_spec_into_aktionen(spec, _teile_single())

    assert len(out) == 6
    parents = [a for a in out if a["parent_phrase_idx"] is None]
    children = [a for a in out if a["parent_phrase_idx"] is not None]
    assert len(parents) == 3
    assert len(children) == 3

    # Each Bohrung-child anchors to its immediately-preceding Tasche-parent
    for i, child in enumerate(children):
        assert child["parent_phrase_idx"] == parents[i]["phrase_idx"]


def test_run_14fa8d40_24_phrases():
    """Run 14fa8d40: 16 Tasche-actions + 8 nested Bohrungen = 24 phrases.
    (Old Step B clumped this to 16, dropping all 8 holes.)"""
    spec = (
        "200mm Würfel, "
        "oben eine Tasche 30x20x10 nach oben um 20mm nach rechts um 20mm versetzt, "
        "oben eine Tasche 20x30x10 die obere Kante von oben 10mm entfernt die linke Seite "
        "von links 10mm entfernt, "
        "oben eine Tasche 30x20x10 von der linken Seite 20mm entfernt die untere Seite "
        "von unten 10mm entfernt, "
        "oben eine Tasche 40x40x10 von der rechten Seite 25mm entfernt von der unteren "
        "Seite 25mm entfernt,,"
        "vorne eine Tasche 30x20x10 nach oben um 20mm nach rechts um 20mm versetzt um 20 "
        "grad im Uhrzeigersinn gedreht, "
        "vorne eine Tasche 20x30x10 die obere Kante von oben 10mm entfernt die linke "
        "Seite von links 10mm entfernt gegen Uhrzeigersinn um 20grad rotiert, "
        "vorne eine Tasche 30x20x10 von der linken Seite 20mm entfernt die untere Seite "
        "von unten 10mm entfernt im Uhrzeigersinn um 20grad, "
        "vorne eine Tasche 40x40x10 von der rechten Seite 25mm entfernt von der unteren "
        "Seite 25mm entfernt 20grad gegen Uhrzeigersinn gedreht,,"
        "links eine Tasche 30x20x10 nach oben um 20mm nach rechts um 20mm versetzt in der "
        "Tasche nach links um 10mm versetzt eine 8mm Bohrung 10tief, "
        "links eine Tasche 20x30x10 die obere Kante von oben 10mm entfernt die linke "
        "Seite von links 10mm entfernt in der Tasche nach oben um 10mm nach rechts um 5mm "
        "eine 8mm Bohrung 10tief, "
        "links eine Tasche 30x20x10 von der linken Seite 20mm entfernt die untere Seite "
        "von unten 10mm entfernt in der Tasche von links 10mm und von der oberen Kante "
        "10mm entfernt 18mm Bohrung 10tief, "
        "links eine Tasche 40x40x10 von der rechten Seite 25mm entfernt von der unteren "
        "Seite 25mm entfernt in der Tasche nach rechts 10mm und nach unten 10mm versetzt "
        "eine Bohrung 18mm 10tief,"
        "rechts eine Tasche 30x20x10 nach oben um 20mm nach rechts um 20mm versetzt um 20 "
        "grad im Uhrzeigersinn gedreht in der Tasche eine Bohrung von rechter Kante 5mm "
        "und von oberer Kante 5mm entfernt eine Bohrung 8mm 10 tief, "
        "rechts eine Tasche 20x30x10 die obere Kante von oben 10mm entfernt die linke "
        "Seite von links 10mm entfernt gegen Uhrzeigersinn um 20grad rotiert in der "
        "tasche nach rechts 5mm versetzt und von der oberen kante 5mm entfernt eine 8mm "
        "bohrung 10 tief, "
        "rechts eine Tasche 30x20x10 von der linken Seite 20mm entfernt die untere Seite "
        "von unten 10mm entfernt im Uhrzeigersinn um 20grad in der tasche von der oberen "
        "seite 5mm entfernt und von der rechten seite 5mm entfernt eine 8mm bohrung 10 tief, "
        "rechts eine Tasche 40x40x10 von der rechten Seite 25mm entfernt von der unteren "
        "Seite 25mm entfernt 20grad gegen Uhrzeigersinn gedreht 10mm nach rechts und "
        "10mm nach oben versetzt sol in der tasche eine 10mm bohrung 10mm tief hin,"
    )
    out = split_spec_into_aktionen(spec, _teile_single())

    parents = [a for a in out if a["parent_phrase_idx"] is None]
    children = [a for a in out if a["parent_phrase_idx"] is not None]
    assert len(parents) == 16   # 4 oben + 4 vorne + 4 links + 4 rechts
    assert len(children) == 8   # links + rechts each carry one nested Bohrung
    assert len(out) == 24

    # phrase_idx is 0..23 contiguous on the single teil
    assert [a["phrase_idx"] for a in out] == list(range(24))
