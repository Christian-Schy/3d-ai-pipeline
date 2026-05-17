"""
tests/agent_regression/test_position_extractor.py — live regression
cases for PositionExtractorAgent.label() — the per-Teil Labeler.

The Labeler splits one part's text into placement_sentences (where the
part sits) vs feature_sentences (what holes/pockets/slots it has). The
gross failure mode is a placement sentence landing in the feature bucket
or vice versa — which silently corrupts both the placer and the feature
chain downstream (ADR 0014 §10.2, Placement-Layer audit).

This suite asserts the bucket PARTITION (each bucket empty / non-empty)
and a minimum feature count where the text unambiguously has N features.
It does not assert exact sentence text — the prompt splits on "und"/","
so counts wobble, but the partition must not.

Run: `pytest tests/agent_regression -m agent_regression -v` (needs Ollama).
"""

from __future__ import annotations

import pytest

from src.agents.position_extractor_agent import PositionExtractorAgent


# `placement` / `feature` = whether that bucket must be non-empty.
# `min_features` = optional lower bound on feature_sentences count.
CASES: list[dict] = [
    {
        "id": "root_cube_features_only",
        "teil_id": "wuerfel",
        "teil_text": "100mm wuerfel mit einer zentralen bohrung d10 durchgehend",
        "placement": False,
        "feature": True,
        "covers": "Root-Teil ohne Platzierung — placement-Bucket muss leer sein",
    },
    {
        "id": "root_cube_two_features",
        "teil_id": "wuerfel",
        "teil_text": "wuerfel 80x80x80, oben eine bohrung d8 zentral, vorne eine tasche 20x20x5",
        "placement": False,
        "feature": True,
        "min_features": 2,
        "covers": "Zwei Features — beide muessen im feature-Bucket landen",
        "xfail": "W1-Befund (ADR 0014 §10.1, Front-Layer): Labeler legt die "
                 "Masse-Wiederholung 'wuerfel 80x80x80' UND das bare Feature-"
                 "Face-Wort 'oben' in den placement-Bucket, statt erstere zu "
                 "droppen und 'oben' beim Feature-Satz zu belassen. Audit im Umbau.",
    },
    {
        "id": "child_plate_placement_and_feature",
        "teil_id": "platte",
        "teil_text": "rechts eine 20x20x10 platte, in der mitte eine bohrung d5",
        "placement": True,
        "feature": True,
        "covers": "Kind-Teil: ein Platzierungs-Satz + ein Feature-Satz, sauber getrennt",
    },
    {
        "id": "child_plate_placement_only",
        "teil_id": "platte",
        "teil_text": "auf der rechten seite eine platte 100x100x20, hochkant buendig mit aussenkante, um 20 grad gedreht",
        "placement": True,
        "feature": False,
        "covers": "Reine Platzierung (Orientierung + Drehung) — feature-Bucket muss leer sein",
    },
]


@pytest.fixture(scope="module")
def position_extractor() -> PositionExtractorAgent:
    return PositionExtractorAgent()


@pytest.mark.agent_regression
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_position_extractor_case(
    position_extractor: PositionExtractorAgent, case: dict, request
) -> None:
    if "xfail" in case:
        request.node.add_marker(pytest.mark.xfail(reason=case["xfail"], strict=False))
    res = position_extractor.label(case["teil_id"], case["teil_text"])
    placement = res.get("placement_sentences", [])
    feature = res.get("feature_sentences", [])

    problems: list[str] = []
    if bool(placement) != case["placement"]:
        problems.append(
            f"placement bucket: got {len(placement)} sentences, "
            f"expected {'non-empty' if case['placement'] else 'empty'}"
        )
    if bool(feature) != case["feature"]:
        problems.append(
            f"feature bucket: got {len(feature)} sentences, "
            f"expected {'non-empty' if case['feature'] else 'empty'}"
        )
    if "min_features" in case and len(feature) < case["min_features"]:
        problems.append(
            f"feature count {len(feature)} < expected min {case['min_features']}"
        )

    if problems:
        raise AssertionError(
            f"\n  case: {case['id']}"
            f"\n  placement: {placement}"
            f"\n  feature:   {feature}"
            f"\n  → {' | '.join(problems)}"
        )
