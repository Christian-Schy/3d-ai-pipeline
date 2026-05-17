"""
tests/agent_regression/test_circular_classifier.py — live regression
cases for the circular_classifier sub-agent (ADR 0009).

What this catches that the unit-tests + pipeline heatmap don't:
- kreis_durchmesser extraction across wordings ("Lochkreis 60mm",
  "Teilkreis-Durchmesser 40mm", "auf einem Teilkreis von 40mm").
- anzahl vs bohr_durchmesser from compact wording ("Lochkreis 8x Ø6").
- A5 corner rule: the teilkreis centre is point-like, so a corner
  phrasing must collapse to two edge distances (abstand_rechts +
  abstand_oben) — same convention as a single hole.

Run: `pytest tests/agent_regression -m agent_regression -v` (needs Ollama).
"""

from __future__ import annotations

import pytest

from src.agents.classifier_sub_agents import CircularClassifier

from tests.agent_regression._lib import assert_hints, default_box


CASES: list[dict] = [
    # ── Kreis-Geometrie ─────────────────────────────────────────────────
    {
        "id": "01_lochkreis_anzahl_teilkreis",
        "phrase": "oben ein lochkreis aus 6 bohrungen 5mm 8 tief auf einem teilkreis von 40mm",
        "expected": {"anzahl": 6, "kreis_durchmesser": 40},
        "covers": "N_coverage baseline; 'auf einem Teilkreis von 40mm' → kreis_durchmesser",
    },
    {
        "id": "02_teilkreis_durchmesser_wording",
        "phrase": "oben ein kreismuster aus 8 bohrungen 6mm durchgehend teilkreis-durchmesser 50mm",
        "expected": {"anzahl": 8, "kreis_durchmesser": 50},
        "covers": "'Teilkreis-Durchmesser 50mm' Wording",
    },
    {
        "id": "03_compact_lochkreis_8x",
        "phrase": "oben ein lochkreis 8x durchmesser 6 auf teilkreis 60mm 10 tief",
        "expected": {"anzahl": 8, "kreis_durchmesser": 60},
        "covers": "Kompakte Schreibweise '8x ... durchmesser 6'",
    },

    # ── Pattern-Center-Bemassung ────────────────────────────────────────
    {
        "id": "04_center_abstand",
        "phrase": "oben ein lochkreis aus 4 bohrungen 5mm 8 tief teilkreis 30mm von linker kante 35mm und von vorderer kante 25mm",
        "expected": {"anzahl": 4, "kreis_durchmesser": 30,
                     "abstand_links": 35, "abstand_vorne": 25},
        "covers": "Teilkreis-Mittelpunkt per abstand_* bemasst",
    },
    {
        "id": "05_center_versatz_aus_mitte",
        "phrase": "oben ein lochkreis aus 6 bohrungen 4mm 6 tief teilkreis 35mm 15mm aus mitte nach rechts versetzt",
        "expected": {"anzahl": 6, "kreis_durchmesser": 35, "versatz_rechts": 15},
        "covers": "Mittelpunkt aus Mitte versetzt → versatz_*",
    },

    # ── A5 Face-Ecke + Versatz ──────────────────────────────────────────
    {
        "id": "06_corner_oben_rechts_A5",
        "phrase": "oben ein lochkreis aus 4 bohrungen 4mm 8 tief teilkreis 20mm in der oberen rechten ecke 15mm nach links und 15mm nach unten versetzt",
        "expected": {"anzahl": 4, "kreis_durchmesser": 20,
                     "abstand_rechts": 15, "abstand_oben": 15},
        "covers": "A5; Teilkreis-Mittelpunkt point-like → Ecke wird zu zwei "
                  "Kanten-Abstaenden. Flippte in W5b zu gruen: das Entfernen des "
                  "anker-Fragments entschlackte den Prompt — das Modell wendet "
                  "die Ecken-Regel jetzt korrekt an (gleicher Effekt wie hole/W2).",
    },
]


@pytest.fixture(scope="module")
def circular_classifier() -> CircularClassifier:
    return CircularClassifier()


# W3 (ADR 0014): circular_classifier emittiert direkt typ=lochkreis.
_EXPECTED_TYP = "lochkreis"


@pytest.mark.agent_regression
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_circular_classifier_case(
    circular_classifier: CircularClassifier, case: dict, request
) -> None:
    if "xfail" in case:
        request.node.add_marker(pytest.mark.xfail(reason=case["xfail"], strict=False))
    res = circular_classifier.classify(
        {"phrase": case["phrase"], "teil_id": "wuerfel", "phrase_idx": 0},
        default_box(),
    )
    if res.get("typ") != _EXPECTED_TYP:
        raise AssertionError(
            f"\n  case: {case['id']}"
            f"\n  typ: got {res.get('typ')!r}, expected {_EXPECTED_TYP!r}"
            f"\n  result: {res}"
        )
    assert_hints(res.get("parameter_hints", {}), case["expected"], case["id"])
