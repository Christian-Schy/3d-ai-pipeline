"""
tests/agent_regression/test_inventar.py — live regression cases for
InventarAgent.extract_teile_only() — Step A of the per-action chain.

Step A's job: turn the spec into the right NUMBER of parts, each with
its raw dimensions taken over verbatim. The historical failure mode
(ADR 0014 §10.1, E_kombo) is part-loss and dimension drift on longer
multi-part specs.

This suite asserts:
- teil_count exactly, and
- per part, the multiset of numeric raw_params values — wording-agnostic
  (x/y/z vs laenge/breite/tiefe vs d/h all reduce to the same numbers),
  so it catches dropped or hallucinated dimensions without coupling to a
  param-key naming convention.

Run: `pytest tests/agent_regression -m agent_regression -v` (needs Ollama).
"""

from __future__ import annotations

import pytest

from src.agents.inventar_agent import InventarAgent


def _dims(raw_params: dict) -> list[float]:
    """Sorted multiset of numeric values in a part's raw_params."""
    return sorted(
        float(v) for v in (raw_params or {}).values()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    )


# `teil_count` exact. `dims` = list of sorted-number multisets, one per
# part, order-independent (matched greedily).
CASES: list[dict] = [
    {
        "id": "single_cube",
        "spec": "ein wuerfel 50x50x50 mm",
        "teil_count": 1,
        "dims": [[50, 50, 50]],
        "covers": "Ein-Teil-Baseline; alle drei Masse uebernommen",
    },
    {
        "id": "single_plate",
        "spec": "eine platte 120x80x15 mm",
        "teil_count": 1,
        "dims": [[15, 80, 120]],
        "covers": "Platte; nicht-kubische Masse",
    },
    {
        "id": "single_cylinder",
        "spec": "ein zylinder durchmesser 40mm hoehe 60mm",
        "teil_count": 1,
        "dims": [[40, 60]],
        "covers": "Zylinder; zwei Masse (Durchmesser + Hoehe)",
    },
    {
        "id": "two_parts_cube_plus_plate",
        "spec": "ein wuerfel 50x50x50, rechts daneben eine platte 30x30x10",
        "teil_count": 2,
        "dims": [[50, 50, 50], [10, 30, 30]],
        "covers": "Zwei-Teile; Multi-Part-Hint 'rechts daneben' aktiv",
    },
    {
        "id": "three_parts",
        "spec": "eine grundplatte 200x100x20, darauf ein wuerfel 40x40x40 und rechts daneben eine leiste 80x20x20",
        "teil_count": 3,
        "dims": [[20, 100, 200], [40, 40, 40], [20, 20, 80]],
        "covers": "E_kombo §10.1; Drei-Teile — Part-Loss-Catch",
    },
]


@pytest.fixture(scope="module")
def inventar() -> InventarAgent:
    return InventarAgent()


@pytest.mark.agent_regression
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_inventar_case(inventar: InventarAgent, case: dict) -> None:
    result = inventar.extract_teile_only(case["spec"])
    teile = result.get("teile", [])

    problems: list[str] = []
    if len(teile) != case["teil_count"]:
        problems.append(
            f"teil_count: got {len(teile)}, expected {case['teil_count']}"
        )
    else:
        # Greedy multiset match — part order is not asserted.
        got = [_dims(t.get("raw_params", {})) for t in teile]
        want = [sorted(map(float, d)) for d in case["dims"]]
        unmatched = list(got)
        for w in want:
            if w in unmatched:
                unmatched.remove(w)
            else:
                problems.append(f"no part with dims {w}")
        for leftover in unmatched:
            problems.append(f"unexpected part dims {leftover}")

    if problems:
        raise AssertionError(
            f"\n  case: {case['id']}"
            f"\n  teile: {teile}"
            f"\n  → {' | '.join(problems)}"
        )
