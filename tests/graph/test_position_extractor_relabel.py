"""tests/graph/test_position_extractor_relabel.py — Post-Filter fuer
position_extractor_node: "auf der/dem <teil_id>"-Saetze landen in
feature_sentences, nicht in placement_sentences.

Verifiziert den Fix vom 2026-05-11 (run f93ae272, EF_kombo_basics):
LLM-Labeler hat Feature-on-self-Saetze in placement gelegt → Platzierer
extrahierte Noise → falsche Plattenposition.
"""
from __future__ import annotations

import pytest

from src.graph.nodes.planning_inventory_nodes import _relabel_features_on_self


def test_ef_canonical_pattern_moves_to_feature():
    """Der konkrete EF-Fail: 'auf der platte oben eine 5mm bohrung...' war
    in placement, soll nach feature."""
    placement = [
        "oben eine platte 60x40x10 zentral",
        "auf der platte oben eine 5mm bohrung 5 tief von der oberen kante 10mm und von der linken kante 8mm entfernt",
        "auf der platte oben eine 5mm bohrung 5 tief obere rechte ecke 5mm nach unten und 8mm nach links versetzt",
    ]
    feature = ["auf der platte mittig eine 5mm bohrung 5 tief"]
    new_p, new_f, moved = _relabel_features_on_self("platte", placement, feature)
    assert new_p == ["oben eine platte 60x40x10 zentral"]
    assert len(new_f) == 3
    assert len(moved) == 2
    assert "auf der platte oben eine 5mm bohrung 5 tief von der oberen kante" in moved[0]


def test_in_der_dem_also_matches():
    placement = [
        "oben drauf platte 60x60x10 zentral",
        "in der platte mittig eine bohrung d10 durchgehend",
        "in dem wuerfel ist eine tasche zentral",  # different teil — bleibt
    ]
    new_p, new_f, moved = _relabel_features_on_self("platte", placement, [])
    assert "oben drauf platte 60x60x10 zentral" in new_p
    assert "in dem wuerfel ist eine tasche zentral" in new_p
    assert "in der platte mittig eine bohrung d10 durchgehend" in new_f
    assert len(moved) == 1


def test_parent_reference_stays_in_placement():
    """Wichtig: 'auf dem wuerfel' beschreibt das Anliegen-Verhaeltnis der
    Platte. Das ist KEIN Feature auf der Platte, bleibt in placement."""
    placement = [
        "oben drauf platte 60x40x10 zentral auf dem wuerfel",
        "auf dem wuerfel oben drauf liegend",
    ]
    new_p, new_f, moved = _relabel_features_on_self("platte", placement, [])
    assert new_p == placement
    assert new_f == []
    assert moved == []


def test_case_insensitive():
    placement = ["Auf der Platte oben eine Bohrung"]
    new_p, new_f, moved = _relabel_features_on_self("platte", placement, [])
    assert new_p == []
    assert "Auf der Platte oben eine Bohrung" in new_f


def test_leading_whitespace_handled():
    placement = ["   auf der platte mittig bohrung"]
    new_p, new_f, moved = _relabel_features_on_self("platte", placement, [])
    assert new_p == []
    assert len(new_f) == 1


def test_no_match_returns_unchanged():
    placement = [
        "oben drauf platte 100x100x20 zentriert",
        "um 10 grad gedreht",
    ]
    new_p, new_f, moved = _relabel_features_on_self("platte", placement, ["foo"])
    assert new_p == placement
    assert new_f == ["foo"]
    assert moved == []


def test_empty_placement():
    new_p, new_f, moved = _relabel_features_on_self("platte", [], ["existing feature"])
    assert new_p == []
    assert new_f == ["existing feature"]
    assert moved == []


def test_substring_match_does_not_fire():
    """'auf der oberen platte' beginnt nicht mit 'auf der platte' — Edge-Case
    der absichtlich NICHT matcht. Wir sind konservativ; wenn das mal wirklich
    nicht reicht, erweitert man die prefixes-Tuple."""
    placement = ["auf der oberen platte sitzt eine bohrung"]
    new_p, new_f, moved = _relabel_features_on_self("platte", placement, [])
    assert new_p == placement
    assert new_f == []
    assert moved == []


def test_teil_id_with_suffix():
    """Wenn teil_id 'platte_1' ist und Spec 'auf der platte_1...' enthaelt
    (selten — meist nutzt der User generic 'platte'), greift die Regel."""
    placement = ["auf der platte_1 oben eine bohrung"]
    new_p, new_f, moved = _relabel_features_on_self("platte_1", placement, [])
    assert new_p == []
    assert len(new_f) == 1


def test_multiple_moves():
    placement = [
        "oben drauf platte 50x50x10 zentral",
        "auf der platte oben eine bohrung",
        "um 30 grad gedreht",
        "auf der platte unten eine tasche",
    ]
    new_p, new_f, moved = _relabel_features_on_self("platte", placement, [])
    assert new_p == ["oben drauf platte 50x50x10 zentral", "um 30 grad gedreht"]
    assert len(new_f) == 2
    assert len(moved) == 2
