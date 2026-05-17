"""
tests/agent_regression/test_platzierer.py — live regression cases for
PositionNormalizerAgent.normalize() — the 'platzierer' 4-step chain
(Frame → Alignment → Anchor → Offset).

The platzierer decides WHERE a child part sits on its parent. Its two
load-bearing outputs are `parent` (which body it attaches to) and
`seite` (which face of that body). `orientierung` and `ausrichtung`
follow. A drift in Frame flips the face; the part lands on the wrong
side and every downstream coordinate is wrong (ADR 0014 §10.2).

This suite asserts the robust fields only — parent, seite, and
orientierung/ausrichtung where the spec states them explicitly. It does
not assert numeric offsets, which depend on the resolver.

Run: `pytest tests/agent_regression -m agent_regression -v` (needs Ollama).
"""

from __future__ import annotations

import pytest

from src.agents.position_normalizer_agent import PositionNormalizerAgent


_WUERFEL = {"id": "wuerfel", "type": "box", "raw_params": {"x": 100, "y": 100, "z": 100}}


def _two_part(child_params: dict) -> list[dict]:
    return [_WUERFEL, {"id": "platte", "type": "box", "raw_params": child_params}]


# `expected` = subset of normalize() output asserted exactly.
CASES: list[dict] = [
    {
        "id": "plate_right_of_cube",
        "spec": "ein wuerfel 100x100x100, rechts daneben eine platte 40x40x10",
        "child_params": {"x": 40, "y": 40, "z": 10},
        "expected": {"parent": "wuerfel", "seite": "rechts"},
        "covers": "Frame: 'rechts daneben' → seite rechts, parent wuerfel",
    },
    {
        "id": "plate_on_top_of_cube",
        "spec": "ein wuerfel 100x100x100, oben drauf eine platte 60x60x15",
        "child_params": {"x": 60, "y": 60, "z": 15},
        "expected": {"parent": "wuerfel", "seite": "oben"},
        "covers": "Frame: 'oben drauf' → seite oben",
    },
    {
        "id": "plate_front_of_cube",
        "spec": "ein wuerfel 100x100x100, vorne eine platte 50x50x12",
        "child_params": {"x": 50, "y": 50, "z": 12},
        "expected": {"parent": "wuerfel", "seite": "vorne"},
        "covers": "Frame: 'vorne' → seite vorne",
    },
    {
        "id": "plate_hochkant_on_top",
        "spec": "ein wuerfel 100x100x100, oben drauf eine platte 80x40x10 hochkant gestellt",
        "child_params": {"x": 80, "y": 40, "z": 10},
        "expected": {"parent": "wuerfel", "seite": "oben", "orientierung": "hochkant"},
        "covers": "Frame: Orientierung 'hochkant' wird mit erfasst",
    },
    {
        "id": "plate_right_centered",
        "spec": "ein wuerfel 100x100x100, rechts eine zentrierte platte 40x40x10",
        "child_params": {"x": 40, "y": 40, "z": 10},
        "expected": {"parent": "wuerfel", "seite": "rechts", "ausrichtung": "zentriert"},
        "covers": "Alignment: 'zentriert' → ausrichtung zentriert",
    },
]


@pytest.fixture(scope="module")
def platzierer() -> PositionNormalizerAgent:
    return PositionNormalizerAgent()


@pytest.mark.agent_regression
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_platzierer_case(platzierer: PositionNormalizerAgent, case: dict) -> None:
    result = platzierer.normalize(
        teil_id="platte",
        teil_type="box",
        teil_params=case["child_params"],
        alle_teile=_two_part(case["child_params"]),
        specification=case["spec"],
    )

    problems: list[str] = []
    for key, want in case["expected"].items():
        if result.get(key) != want:
            problems.append(f"{key}: got {result.get(key)!r}, expected {want!r}")

    if problems:
        raise AssertionError(
            f"\n  case: {case['id']}"
            f"\n  result: {result}"
            f"\n  → {' | '.join(problems)}"
        )
