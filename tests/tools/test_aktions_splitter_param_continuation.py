"""tests/tools/test_aktions_splitter_param_continuation.py

Verifiziert die Post-Splitter-Coherence-Heuristik (Variante A, 2026-05-12):
comma-Fragments ohne Feature-Trigger die nur Parameter (Tiefe, Versatz,
Achse, Drehung, Kantenabstand) ergaenzen, werden an die vorherige Aktion
desselben teil_id angehaengt statt zu droppen.

Adressiert den B3 v1 Bug (run f1744b99): "10 tief" wurde verworfen → depth
fehlte downstream → feature_definierer FAIL.
"""
from __future__ import annotations

from src.tools.aktions_splitter import split_spec_into_aktionen


def _phrases(spec: str, teile=None):
    teile = teile or [{"id": "wuerfel"}]
    return [a["phrase"] for a in split_spec_into_aktionen(spec, teile)]


def test_b3_v1_tail_no_longer_dropped():
    """Run f1744b99 Pattern: 'X tief' und 'aus mitte Y nach Z' wurden
    bisher als Comma-Fragmente ohne Feature verworfen."""
    spec = ("200mm wuerfel, oben eine 18mm bohrung 10mm von oberer kante, "
            "90mm aus mitte nach links, 10 tief")
    out = _phrases(spec)
    assert len(out) == 1
    p = out[0]
    assert "10mm von oberer kante" in p
    assert "90mm aus mitte nach links" in p
    assert "10 tief" in p


def test_depth_only_param_appends_to_prev_action():
    spec = "100mm wuerfel, oben eine 8mm bohrung von links 20mm entfernt, 10 tief"
    out = _phrases(spec)
    assert len(out) == 1
    assert out[0].endswith("10 tief")


def test_axis_continuation_appends_to_nut():
    spec = "100mm wuerfel, oben eine nut 5x5 zentral, entlang x-achse"
    out = _phrases(spec)
    assert len(out) == 1
    assert "entlang x-achse" in out[0]


def test_rotation_continuation_appends():
    spec = "100mm wuerfel, oben eine tasche 30x20x5 zentral, 15 grad gegen uhrzeigersinn"
    out = _phrases(spec)
    assert len(out) == 1
    assert "15 grad gegen uhrzeigersinn" in out[0]


def test_separate_feature_phrases_not_merged():
    """Zwei eigenstaendige Bohrungs-Phrasen duerfen NICHT zusammengezogen werden."""
    spec = "100mm wuerfel, oben eine 10mm bohrung 5 tief, oben eine 8mm bohrung 3 tief"
    out = _phrases(spec)
    assert len(out) == 2


def test_corner_anchor_prefix_still_works():
    """Regressions-Schutz: bestehender pre-feature anchor prefix verhalten
    bleibt unveraendert (uebernimmt 'oben: obere rechte ecke ...' Block)."""
    spec = ("200mm wuerfel; oben: obere rechte ecke der oberseite, "
            "20mm nach unten und 30mm nach links versetzt eine 18mm bohrung 10 tief")
    out = _phrases(spec)
    # Phrase enthaelt sowohl den Anker als auch die Bohrung — der existierende
    # _is_pre_feature_anchor_prefix-Pfad faengt das ab.
    assert len(out) == 1
    assert "obere rechte ecke" in out[0]
    assert "bohrung" in out[0]


def test_param_fragment_does_not_attach_across_teile():
    """Wenn das vorherige Fragment einem anderen teil_id gehoert, soll
    Parameter-Continuation NICHT cross-teil anhaengen."""
    spec = ("50mm wuerfel, rechts platte 40x40x20 zentriert, "
            "10 tief, oben eine 5mm bohrung")
    teile = [{"id": "wuerfel"}, {"id": "platte"}]
    out = split_spec_into_aktionen(spec, teile)
    # "10 tief" geht entweder weg (kein Feature, anderer Kontext)
    # oder haengt an Platte-Aktion. Wichtig: bricht nicht in Bohrung.
    bohrungen = [a for a in out if "bohrung" in a["phrase"]]
    assert len(bohrungen) == 1
    assert "10 tief" not in bohrungen[0]["phrase"]


def test_param_fragment_dropped_if_no_prior_action():
    """Ein Parameter-Fragment ohne vorherige Aktion (z.B. Spec faengt damit
    an) darf nicht zu einer Phantom-Aktion werden."""
    spec = "10 tief"
    out = _phrases(spec)
    assert out == []


def test_von_seite_distance_continuation():
    spec = "100mm wuerfel, oben eine tasche 30x20x5, von linker kante 10mm entfernt"
    out = _phrases(spec)
    assert len(out) == 1
    assert "von linker kante 10mm entfernt" in out[0]


def test_im_uhrzeigersinn_alone_continuation():
    spec = "100mm wuerfel, oben eine tasche 30x20x5, 20 grad im uhrzeigersinn"
    out = _phrases(spec)
    assert len(out) == 1
    assert "20 grad im uhrzeigersinn" in out[0]
