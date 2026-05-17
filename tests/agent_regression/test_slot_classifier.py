"""
tests/agent_regression/test_slot_classifier.py — live regression cases
for the slot_classifier sub-agent.

What this catches that the unit-tests + pipeline heatmap don't:
- abstand vs kante wording (slot centre-to-edge vs slot-edge-to-edge);
  the prompt's "im Zweifel abstand_*" rule must hold — kante_* only on an
  explicit "Nut-Kante" phrasing.
- Endpoint model (Konvention 21 / N04): a slot given by two endpoints
  must emit anfang_<dir>/ende_<dir> and NO laenge — the agent must not
  pre-compute the length.
- richtung extraction from "entlang X/Y" wording.
- kante_* over-emission for plain "von X Kante" phrasings.

Run: `pytest tests/agent_regression -m agent_regression -v` (needs Ollama).
"""

from __future__ import annotations

import pytest

from src.agents.classifier_sub_agents import SlotClassifier

from tests.agent_regression._lib import assert_positioning_hints, default_box


# `expected` = positioning subset asserted exactly (incl. over-emission
# guard). `richtung` = optional exact axis check. Size keys
# (laenge/breite/tiefe) intentionally not asserted here.
CASES: list[dict] = [
    # ── A1 baseline: richtung + abstand default ─────────────────────────
    {
        "id": "01_richtung_x_abstand_default",
        "phrase": "oben eine nut 5x5 entlang der x-achse laenge 60mm von vorderer kante 30mm",
        "richtung": "x",
        "expected": {"abstand_vorne": 30},
        "covers": "N_coverage baseline; 'von X Kante' → abstand_* (Nut-Mitte)",
    },
    {
        "id": "02_richtung_y_abstand_default",
        "phrase": "oben eine nut 6x4 entlang y-achse laenge 50mm von linker kante 20mm",
        "richtung": "y",
        "expected": {"abstand_links": 20},
        "covers": "richtung y; abstand auf der Querachse",
    },

    # ── Nut-Kante (edge-to-edge) — kante_* nur bei explizitem Wort ───────
    {
        "id": "03_nut_kante_edge_to_edge",
        "phrase": "oben eine nut 5x5 entlang x-achse laenge 40mm die vordere nut-kante 12mm vom vorderen rand",
        "richtung": "x",
        "expected": {"kante_vorne": 12},
        "covers": "explizite 'Nut-Kante' → kante_*; A2 edge-to-edge",
    },
    {
        "id": "04_plain_kante_stays_abstand",
        "phrase": "oben eine nut 5x3 entlang x-achse laenge 50mm 25mm von der hinteren kante entfernt",
        "richtung": "x",
        "expected": {"abstand_hinten": 25},
        "covers": "'von der hinteren Kante' OHNE 'Nut-Kante' → abstand_* (kante_* over-emission catch)",
    },

    # ── Endpoint model (Konvention 21 / N04) ────────────────────────────
    {
        "id": "05_endpoints_links",
        "phrase": "oben eine nut 5x3 anfangspunkt 20mm von linker kante endpunkt 80mm von linker kante",
        "richtung": "x",
        "expected": {"anfang_links": 20, "ende_links": 80},
        "covers": "N04 Endpunkt-Modell; anfang_/ende_ an derselben Kante, KEIN laenge — Achse aus Kanten abgeleitet",
    },
    {
        "id": "06_endpoints_vorne",
        "phrase": "oben eine nut 6x4 anfangspunkt 15mm von vorderer kante endpunkt 70mm von vorderer kante",
        "richtung": "y",
        "expected": {"anfang_vorne": 15, "ende_vorne": 70},
        "covers": "Endpunkte an vorderer Kante → richtung y",
    },

    # ── Rotation ────────────────────────────────────────────────────────
    {
        "id": "07_rotation_ccw",
        "phrase": "oben eine zentrierte nut 5x5 laenge 40mm um 30 grad gedreht",
        "expected": {"rotation_deg": 30},
        "covers": "Rotation CCW = positiv; zentriert → keine Positionierung",
    },

    # ── Centered baseline (negative case) ───────────────────────────────
    {
        "id": "08_zentriert_no_positioning",
        "phrase": "oben eine zentrierte nut 5x5 entlang x-achse laenge 50mm",
        "richtung": "x",
        "expected": {},
        "covers": "zentriert → keine Positionierungs-Keys (Over-Emission catch)",
    },

    # ── Voice / informal wording ────────────────────────────────────────
    {
        "id": "09_voice_informal",
        "phrase": "oben nut 5 mal 5 entlang x laenge 45 von vorne 22",
        "richtung": "x",
        "expected": {"abstand_vorne": 22},
        "covers": "Voice-Variante; 'entlang x' kurz, bare Zahlen",
    },
]


@pytest.fixture(scope="module")
def slot_classifier() -> SlotClassifier:
    return SlotClassifier()


@pytest.mark.agent_regression
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_slot_classifier_case(slot_classifier: SlotClassifier, case: dict) -> None:
    res = slot_classifier.classify(
        {"phrase": case["phrase"], "teil_id": "wuerfel", "phrase_idx": 0},
        default_box(),
    )
    hints = res.get("parameter_hints", {})

    if "richtung" in case and hints.get("richtung") != case["richtung"]:
        raise AssertionError(
            f"\n  case: {case['id']}"
            f"\n  richtung: got {hints.get('richtung')!r}, expected {case['richtung']!r}"
            f"\n  hints: {hints}"
        )

    assert_positioning_hints(hints, case["expected"], case["id"])
