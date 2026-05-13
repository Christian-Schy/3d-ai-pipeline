"""tests/tools/test_teil_splitter.py — Deterministic part-declaration splitter (ADR 0007).

Verifiziert, dass `split_spec_into_teil_declarations` lange Multi-Part-Specs
in eine Phrase pro Teil-Deklaration zerlegt — ohne mitten in einer Info
abzuschneiden, ohne Referenzen ("der platte", "des wuerfels") faelschlich
als neue Teile zu zaehlen.
"""
from __future__ import annotations

from src.tools.teil_splitter import (
    split_spec_into_teil_declarations as split,
    _is_part_declaration,
)


def test_single_part_one_declaration():
    out = split("200mm wuerfel, oben eine 10mm bohrung 5 tief")
    assert len(out) == 1
    assert out[0].startswith("200mm wuerfel")
    # Feature fragment gets appended, not split off as a new part.
    assert "bohrung" in out[0]


def test_e_kombo_thirteen_plate_declarations():
    """Der E_kombo-Fail: 13 fast-identische 'platte 80x40x20'-Deklarationen."""
    spec = ("100mm wuerfel, "
            "vorne soll eine platte 80x40x20 zentral hin, "
            "vorne soll eine platte 80x40x20, die 80x40 seite liegt auf, obere rechte ecke der platte auf obere rechte ecke des wuerfels, "
            "vorne soll eine platte 80x40x20, die 80x40 seite liegt auf, obere rechte ecke der platte auf obere rechte ecke des wuerfels, 10mm nach links versetzt, "
            "oben soll eine platte 80x40x20, die 80x40 seite liegt auf, zentral, "
            "rechts soll eine platte 80x40x20, die 80x40 seite liegt auf, zentral")
    out = split(spec)
    # 1 wuerfel + 5 plate declarations = 6
    assert len(out) == 6
    assert out[0].startswith("100mm wuerfel")
    assert all("platte 80x40x20" in p for p in out[1:])


def test_reference_not_counted_as_new_part():
    """'obere rechte ecke der platte auf obere rechte ecke des wuerfels' hat
    Teil-Keywords aber KEINE Dimension -> kein neues Teil, wird angehaengt."""
    spec = ("100mm wuerfel, vorne soll eine platte 80x40x20, "
            "obere rechte ecke der platte auf obere rechte ecke des wuerfels, "
            "10mm nach links versetzt")
    out = split(spec)
    assert len(out) == 2  # wuerfel + platte (refs/offsets appended)
    assert "obere rechte ecke der platte" in out[1]
    assert "10mm nach links versetzt" in out[1]


def test_orientation_fragment_appended():
    """'die 80x40 seite liegt auf' hat eine Dim-aehnliche '80x40' aber kein
    Teil-Keyword -> kein neues Teil."""
    assert not _is_part_declaration("die 80x40 seite liegt auf")
    spec = "50mm wuerfel, oben drauf platte 100x100x20, die 100x20 seite liegt auf, zentriert"
    out = split(spec)
    assert len(out) == 2
    assert "die 100x20 seite liegt auf" in out[1]


def test_is_part_declaration_positive_cases():
    assert _is_part_declaration("100mm wuerfel")
    assert _is_part_declaration("vorne soll eine platte 80x40x20 zentral")
    assert _is_part_declaration("platte 60x40x10 oben")
    assert _is_part_declaration("zylinder Ø50 hochkant")
    assert _is_part_declaration("eine box 30 x 20 x 10 daneben")
    assert _is_part_declaration("80x40x20 platte")


def test_is_part_declaration_negative_cases():
    assert not _is_part_declaration("oben eine bohrung 10mm 5 tief")     # bohrung != part
    assert not _is_part_declaration("die 80x40 seite liegt auf")          # no part kw
    assert not _is_part_declaration("obere rechte ecke der platte")       # part kw, no dim
    assert not _is_part_declaration("10mm nach links versetzt")           # dim, no part kw
    assert not _is_part_declaration("zentral 30 grad gedreht")            # neither


def test_feature_on_base_part_appended_not_new():
    """'oben eine bohrung ...' nach '100mm wuerfel' wird an den Wuerfel
    angehaengt (Step-A-Mikro-Call ignoriert Features ohnehin)."""
    spec = "100mm wuerfel, oben eine 10mm bohrung 5 tief, vorne eine platte 50x50x10"
    out = split(spec)
    assert len(out) == 2  # wuerfel(+bohrung) + platte
    assert "bohrung" in out[0]
    assert out[1].startswith("vorne eine platte 50x50x10")


def test_empty_spec():
    assert split("") == []
    assert split("   ") == []


def test_no_part_declaration_returns_empty():
    """Spec ohne erkennbare Teil-Deklaration -> [] -> Caller faellt auf
    One-Shot zurueck."""
    assert split("mach was schoenes mit einer bohrung") == []


def test_leading_non_declaration_fragment_dropped():
    out = split("zuerst etwas text, dann 100mm wuerfel, oben eine bohrung")
    assert len(out) == 1
    # The "dann 100mm wuerfel" segment is the declaration (it carries the
    # dims); a stray "dann" prefix is harmless — the Step-A micro-call
    # extracts the wuerfel and ignores it.
    assert "100mm wuerfel" in out[0]
    assert "zuerst etwas text" not in out[0]


def test_semicolon_separator():
    spec = "100mm wuerfel; vorne platte 50x50x10; oben platte 40x40x20"
    out = split(spec)
    assert len(out) == 3
