"""
tests/agent_regression/test_pocket_classifier.py — live regression cases
for the pocket_classifier sub-agent.

What this catches that the unit-tests + pipeline heatmap don't:
- Prompt-vs-demo drift after a retrain (e.g. kante_* over-emission for
  plain "von X kante" phrasings).
- Spatial-inversion failures in corner-Versatz wordings (e.g.
  "obere rechte Ecke … nach links" → must map to abstand_rechts, not
  abstand_links).
- Bündig / edge-to-edge wording (kante_<dir>: 0).
- Voice-style informal numbers + missing prepositions.

Run: `pytest tests/agent_regression -m agent_regression -v` (needs Ollama).
"""

from __future__ import annotations

import pytest

from src.agents.classifier_sub_agents import PocketClassifier

from tests.agent_regression._lib import assert_positioning_hints, default_box


# Each case lists ONLY the positioning keys the case is asserting on
# (plus rotation_deg). Size keys (laenge/breite/tiefe) are intentionally
# left out — see _lib.assert_positioning_hints docstring.
CASES: list[dict] = [
    # ── A1 baseline: abstand default, two directions ────────────────────
    {
        "id": "01_abstand_two_dirs_default",
        "phrase": "oben eine tasche 30x20x10 von linker kante 15mm und von vorderer kante 25mm",
        "expected": {"abstand_links": 15, "abstand_vorne": 25},
        "covers": "T_coverage t01 baseline; Default A1 für 'von X Kante' ohne 'Taschen-Kante'",
    },

    # ── T06: per-Richtung A1/A2-Mix — kante nur bei expliziter Taschen-Kante ─
    {
        "id": "06_taschen_kante_plus_abstand",
        "phrase": "rechts eine tasche 20x15x8 die obere taschen-kante 10mm vom oberen rand und von linker kante 18mm",
        "expected": {"kante_oben": 10, "abstand_links": 18},
        "covers": "T_coverage t06; A2 nur wo 'Taschen-Kante' explizit, A1 sonst",
    },

    # ── T02 / Edge-to-edge double — beide Richtungen mit Taschen-Kante ──
    {
        "id": "02_edge_to_edge_double_taschen_kante",
        "phrase": "vorne eine tasche 25x18x8 die linke taschen-kante 12mm vom linken rand und die untere taschen-kante 15mm vom unteren rand",
        "expected": {"kante_links": 12, "kante_unten": 15},
        "covers": "T_coverage t02; beide Richtungen 'Taschen-Kante' → kante_*",
    },

    # ── T08 Ecken-Regel: alle 4 Ecken, Bezugskanten = Eck-Kanten ────────
    {
        "id": "08a_corner_oben_rechts_T_coverage",
        "phrase": "unten eine tasche 25x18x6 in der oberen rechten ecke 22mm nach links und 18mm nach unten versetzt",
        "expected": {"abstand_rechts": 22, "abstand_oben": 18},
        "covers": "T_coverage t08; Ecke oben-rechts → abstand_oben + abstand_rechts; 'nach links/unten' nur Bewegungsrichtung",
    },
    {
        "id": "08b_corner_oben_rechts_T_kombo_reordered",
        "phrase": "oben eine tasche 30x20x10 obere rechte ecke 10mm nach unten und 20mm nach links versetzt",
        "expected": {"abstand_oben": 10, "abstand_rechts": 20},
        "covers": "T_kombo t08; gleiche Ecke, 'nach unten' zuerst, kein 'in der' Präfix",
    },
    {
        "id": "08c_corner_oben_links",
        "phrase": "vorne eine tasche 20x15x6 obere linke ecke 16mm nach rechts und 14mm nach unten versetzt",
        "expected": {"abstand_links": 16, "abstand_oben": 14},
        "covers": "Ecke oben-links → abstand_oben + abstand_links",
    },
    {
        "id": "08d_corner_unten_links",
        "phrase": "oben eine tasche 25x15x8 in der unteren linken ecke der seite 30mm nach rechts und 20mm nach oben versetzt",
        "expected": {"abstand_links": 30, "abstand_unten": 20},
        "covers": "Ecke unten-links → abstand_unten + abstand_links",
    },
    {
        "id": "08e_corner_unten_rechts",
        "phrase": "rechts eine tasche 24x16x7 in der unteren rechten ecke 17mm nach links und 13mm nach oben versetzt",
        "expected": {"abstand_rechts": 17, "abstand_unten": 13},
        "covers": "Ecke unten-rechts → abstand_unten + abstand_rechts",
    },
    {
        "id": "08f_corner_reverse_wording",
        "phrase": "hinten eine tasche 20x14x6 an der rechten oberen ecke 9mm nach unten und 16mm nach links versetzt",
        "expected": {"abstand_oben": 9, "abstand_rechts": 16},
        "covers": "Ecke-Wortfolge invertiert ('rechte obere'), 'an der' statt 'in der'",
    },

    # ── T09: abstand + versatz (mixed conventions on different axes) ────
    {
        "id": "09_abstand_plus_versatz_aus_mitte",
        "phrase": "oben eine tasche 25x20x8 von linker kante 25mm und 10mm aus mitte nach hinten versetzt",
        "expected": {"abstand_links": 25, "versatz_hinten": 10},
        "covers": "T_coverage t09; A1 auf einer Achse + A3 (versatz aus mitte) auf der anderen — kante_* darf NICHT auftauchen",
    },

    # ── T10: abstand + rotation (CCW positive) ──────────────────────────
    {
        "id": "10_abstand_plus_rotation_ccw",
        "phrase": "oben eine tasche 30x15x8 um 30 grad gedreht von linker kante 40mm und von vorderer kante 30mm",
        "expected": {"abstand_links": 40, "abstand_vorne": 30, "rotation_deg": 30},
        "covers": "T_coverage t10; A1 auf beiden Achsen + Rotation (default CCW = positiv)",
    },

    # ── Rotation CW (negative) ──────────────────────────────────────────
    {
        "id": "11_rotation_cw_negative_no_positioning",
        "phrase": "oben eine zentrierte tasche 25x18x10 um 20 grad im uhrzeigersinn gedreht",
        "expected": {"rotation_deg": -20},
        "covers": "T_coverage t11; CW → negative rotation_deg; zentriert → keine Position",
    },

    # ── T12: bündig (kante_<dir>: 0) + abstand auf anderer Achse ────────
    {
        "id": "12a_buendig_oben_plus_abstand_rechts",
        "phrase": "vorne eine tasche 25x18x8 oben buendig anliegend und 20mm von der rechten kante",
        "expected": {"kante_oben": 0, "abstand_rechts": 20},
        "covers": "T_coverage t12; 'oben buendig' → kante_oben:0; 'von rechter Kante' bleibt abstand_*",
    },
    {
        "id": "12b_buendig_rechts_plus_abstand_vorne",
        "phrase": "oben eine tasche 30x20x10 rechts buendig anliegend und 25mm von der vorderen kante",
        "expected": {"kante_rechts": 0, "abstand_vorne": 25},
        "covers": "Bündig auf anderer Seite — kante_rechts:0",
    },

    # ── Centered baseline (negative case: no positioning at all) ────────
    {
        "id": "04_zentriert_no_positioning",
        "phrase": "hinten eine zentrierte tasche 50x30x8",
        "expected": {},
        "covers": "T_coverage t04; zentriert → keine Positionierungs-Keys (regression catch für Over-Emission)",
    },

    # ── Voice / informal wording ────────────────────────────────────────
    {
        "id": "voice_corner_informal_numbers",
        "phrase": "oben eine tasche 30 mal 20 mal 10 obere rechte ecke 12 nach unten 18 nach links versetzt",
        "expected": {"abstand_oben": 12, "abstand_rechts": 18},
        "covers": "Voice-Variante; '30 mal 20 mal 10' statt '30x20x10', ohne 'und' zwischen den Versatz-Werten",
    },
]


@pytest.fixture(scope="module")
def pocket_classifier() -> PocketClassifier:
    return PocketClassifier()


@pytest.mark.agent_regression
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_pocket_classifier_case(pocket_classifier: PocketClassifier, case: dict) -> None:
    res = pocket_classifier.classify(
        {"phrase": case["phrase"], "teil_id": "wuerfel", "phrase_idx": 0},
        default_box(),
    )
    assert_positioning_hints(
        res.get("parameter_hints", {}),
        case["expected"],
        case["id"],
    )
