"""
tests/agent_regression/test_anchor_classifier.py — live regression cases
for the AnchorClassifier micro-agent (ADR 0014 W5b).

The AnchorClassifier has exactly ONE job: decide whether an action
phrase carries an anchor (an explicit "<feature-punkt> AUF <parent-
punkt>" reference) and, if so, emit `anker_kind` / `anker_eltern`. It
was split out of the typ-classifiers because the anchor disambiguation
as a parallel sixth task stalled the small model (ADR 0014 §13).

The hardest cases are the NEGATIVES: a bare corner / edge mention is
positioning, not an anchor. Over-emitting an anchor there would override
the classifier's coordinate positioning — those cases assert `{}`.

Run: `pytest tests/agent_regression -m agent_regression -v` (needs Ollama).
"""

from __future__ import annotations

import pytest

from src.agents.classifier_sub_agents import AnchorClassifier


# `expected` = exact return value of classify_anchor(). {} means "no anchor".
CASES: list[dict] = [
    # ── Echte Anker ─────────────────────────────────────────────────────
    {
        "id": "parent_edge_liegt_auf",
        "phrase": "oben eine nut 5x5 entlang y-achse laenge 40mm liegt auf rechter kante an",
        "expected": {"anker_eltern": "right_edge"},
        "covers": "'liegt auf rechter Kante an' → Parent-Kanten-Anker, kind=center (weggelassen)",
    },
    {
        "id": "parent_edge_obere",
        "phrase": "oben eine bohrung 6mm liegt auf der oberen kante des wuerfels",
        "expected": {"anker_eltern": "top_edge"},
        "covers": "'auf der oberen Kante des Wuerfels' → top_edge",
    },
    {
        "id": "corner_to_corner",
        "phrase": "oben eine tasche 30x20x10 obere rechte ecke der tasche auf obere rechte ecke des wuerfels",
        "expected": {"anker_kind": "top_right", "anker_eltern": "top_right"},
        "covers": "Ecke-der-Tasche AUF Ecke-des-Wuerfels → beide top_right",
    },
    {
        "id": "edge_to_edge_child",
        "phrase": "oben eine 5mm bohrung rechte kante der bohrung auf rechte kante der platte",
        "expected": {"anker_kind": "right_edge", "anker_eltern": "right_edge"},
        "covers": "Kante-der-Bohrung AUF Kante-der-Platte → beide right_edge",
    },

    # ── Anti-Faelle: KEIN Anker (Positionierung) ────────────────────────
    {
        "id": "negative_bare_corner",
        "phrase": "unten eine tasche 25x18x6 in der oberen rechten ecke 22mm nach links und 18mm nach unten versetzt",
        "expected": {},
        "covers": "Bare Ecke + Versatz = Positionierung (Ecken-Regel), KEIN Anker",
    },
    {
        "id": "negative_von_kante",
        "phrase": "oben eine tasche 30x20x10 von linker kante 15mm und von vorderer kante 25mm",
        "expected": {},
        "covers": "'von linker Kante 15mm' = abstand_*, KEIN Anker",
    },
    {
        "id": "negative_taschen_kante",
        "phrase": "vorne eine tasche 25x18x8 die obere taschen-kante 10mm vom oberen rand",
        "expected": {},
        "covers": "'Taschen-Kante vom Rand' = kante_* edge-to-edge, KEIN Anker (kein Parent-Punkt)",
    },
    {
        "id": "negative_centered",
        "phrase": "hinten eine zentrierte tasche 50x30x8",
        "expected": {},
        "covers": "Zentriert → kein Anker",
    },
]


@pytest.fixture(scope="module")
def anchor_classifier() -> AnchorClassifier:
    return AnchorClassifier()


@pytest.mark.agent_regression
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_anchor_classifier_case(
    anchor_classifier: AnchorClassifier, case: dict
) -> None:
    result = anchor_classifier.classify_anchor(case["phrase"])
    if result != case["expected"]:
        raise AssertionError(
            f"\n  case:     {case['id']}"
            f"\n  phrase:   {case['phrase']}"
            f"\n  got:      {result}"
            f"\n  expected: {case['expected']}"
        )
