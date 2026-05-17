"""
tests/agent_regression/test_linear_classifier.py — live regression cases
for the linear_classifier sub-agent (ADR 0009).

What this catches that the unit-tests + pipeline heatmap don't:
- anzahl + abstand (Lochabstand) extraction for Bohrungsreihen.
- richtung extraction both from "entlang X" and from directional verbs
  ("verlaeuft nach hinten" → y, "nach rechts" → x).
- Pattern-center positioning vs the per-hole abstand (Lochabstand) — the
  agent must not confuse the row's spacing with its placement.

Run: `pytest tests/agent_regression -m agent_regression -v` (needs Ollama).
"""

from __future__ import annotations

import pytest

from src.agents.classifier_sub_agents import LinearClassifier

from tests.agent_regression._lib import assert_hints, default_box


CASES: list[dict] = [
    # ── Reihen-Geometrie + richtung aus 'entlang' ───────────────────────
    {
        "id": "01_reihe_entlang_x_abstand",
        "phrase": "oben eine bohrungsreihe aus 5 bohrungen 5mm 8 tief entlang der x-achse abstand 20mm",
        "expected": {"anzahl": 5, "abstand": 20, "richtung": "x"},
        "covers": "N_coverage baseline; Reihe entlang X mit Lochabstand",
    },
    {
        "id": "02_lochabstand_wording",
        "phrase": "oben eine lochreihe aus 4 bohrungen 6mm durchgehend entlang y-achse im lochabstand 15mm",
        "expected": {"anzahl": 4, "abstand": 15, "richtung": "y"},
        "covers": "'im Lochabstand 15mm' Wording → abstand",
    },

    # ── richtung aus Richtungs-Verb ─────────────────────────────────────
    {
        "id": "03_richtung_verb_hinten",
        "phrase": "oben eine reihe aus 6 bohrungen 5mm 8 tief die nach hinten verlaeuft abstand 18mm",
        "expected": {"anzahl": 6, "abstand": 18, "richtung": "y"},
        "covers": "Richtungs-Verb 'verlaeuft nach hinten' → richtung y",
    },
    {
        "id": "04_richtung_verb_rechts",
        "phrase": "oben eine bohrungsreihe aus 5 bohrungen 4mm 6 tief nach rechts verlaufend abstand 22mm",
        "expected": {"anzahl": 5, "abstand": 22, "richtung": "x"},
        "covers": "Richtungs-Verb 'nach rechts' → richtung x",
    },

    # ── Pattern-Center-Bemassung ────────────────────────────────────────
    {
        "id": "05_center_abstand",
        "phrase": "oben eine bohrungsreihe aus 4 bohrungen 5mm 8 tief entlang x-achse abstand 20mm von vorderer kante 30mm",
        "expected": {"anzahl": 4, "abstand": 20, "richtung": "x", "abstand_vorne": 30},
        "covers": "Reihen-Lochabstand (abstand) vs Pattern-Position (abstand_vorne) getrennt",
    },

    # ── Rotation ────────────────────────────────────────────────────────
    {
        "id": "06_rotation_cw",
        "phrase": "oben eine zentrierte bohrungsreihe aus 5 bohrungen 5mm 8 tief entlang x-achse abstand 15mm um 20 grad im uhrzeigersinn gedreht",
        "expected": {"anzahl": 5, "abstand": 15, "richtung": "x", "rotation_deg": -20},
        "covers": "Rotation CW → negative rotation_deg",
    },
]


@pytest.fixture(scope="module")
def linear_classifier() -> LinearClassifier:
    return LinearClassifier()


# W3 (ADR 0014): linear_classifier emittiert direkt typ=bohrungsreihe.
_EXPECTED_TYP = "bohrungsreihe"


@pytest.mark.agent_regression
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_linear_classifier_case(linear_classifier: LinearClassifier, case: dict) -> None:
    res = linear_classifier.classify(
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
