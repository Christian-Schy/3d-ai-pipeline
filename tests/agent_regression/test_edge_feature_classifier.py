"""
tests/agent_regression/test_edge_feature_classifier.py — live regression
cases for the edge_feature_classifier sub-agent.

What this catches that the unit-tests + pipeline heatmap don't:
- typ disambiguation fase vs rundung across wordings ("anfasen",
  "abrunden", "verrunden", "Radius").
- The correct size key per type: a fase carries `groesse`, a rundung
  carries `radius` — swapping them breaks the template downstream.

Run: `pytest tests/agent_regression -m agent_regression -v` (needs Ollama).
"""

from __future__ import annotations

import pytest

from src.agents.classifier_sub_agents import EdgeFeatureClassifier

from tests.agent_regression._lib import assert_hints, default_box


# `typ` = exact match. `hints` = hint subset asserted exactly.
CASES: list[dict] = [
    {
        "id": "01_fase_groesse",
        "phrase": "oben eine fase 2mm an der vorderen kante",
        "typ": "fase",
        "hints": {"groesse": 2},
        "covers": "Cap 2.0; 'Fase 2mm' → typ fase, groesse",
    },
    {
        "id": "02_fase_anfasen_verb",
        "phrase": "die obere kante mit 1.5mm anfasen",
        "typ": "fase",
        "hints": {"groesse": 1.5},
        "covers": "Verb 'anfasen' → typ fase; Dezimalwert",
    },
    {
        "id": "03_rundung_radius",
        "phrase": "oben eine rundung mit radius 3mm an allen kanten",
        "typ": "rundung",
        "hints": {"radius": 3},
        "covers": "'Rundung mit Radius 3mm' → typ rundung, radius",
    },
    {
        "id": "04_rundung_abrunden_verb",
        "phrase": "die rechte kante mit 5mm abrunden",
        "typ": "rundung",
        "hints": {"radius": 5},
        "covers": "Verb 'abrunden' → typ rundung; Wert ohne Wort 'Radius' → radius",
    },
    {
        "id": "05_rundung_verrunden_verb",
        "phrase": "alle kanten verrunden r4",
        "typ": "rundung",
        "hints": {"radius": 4},
        "covers": "Verb 'verrunden' + kompaktes 'r4' → typ rundung, radius",
    },
]


@pytest.fixture(scope="module")
def edge_feature_classifier() -> EdgeFeatureClassifier:
    return EdgeFeatureClassifier()


@pytest.mark.agent_regression
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_edge_feature_classifier_case(
    edge_feature_classifier: EdgeFeatureClassifier, case: dict
) -> None:
    res = edge_feature_classifier.classify(
        {"phrase": case["phrase"], "teil_id": "wuerfel", "phrase_idx": 0},
        default_box(),
    )
    if res.get("typ") != case["typ"]:
        raise AssertionError(
            f"\n  case: {case['id']}"
            f"\n  typ: got {res.get('typ')!r}, expected {case['typ']!r}"
            f"\n  result: {res}"
        )
    assert_hints(res.get("parameter_hints", {}), case["hints"], case["id"])
