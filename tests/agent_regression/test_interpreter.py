"""
tests/agent_regression/test_interpreter.py — live regression cases for
InterpreterAgent.process().

The Interpreter's one load-bearing decision is the `is_complete` gate:
a request with every critical dimension present must pass straight
through (is_complete=True, no question); a request missing a critical
dimension must stop and ask (is_complete=False, non-empty question).

This suite asserts ONLY that boolean gate + question presence — not the
free-text `specification`, which legitimately varies wording run to run.

W1 discovery role (ADR 0014 §10.1): the Front-Layer is not yet audited
for re-derivation. A drift here (over-asking, or waving through an
underspecified part) shows up as a flipped gate.

Run: `pytest tests/agent_regression -m agent_regression -v` (needs Ollama).
"""

from __future__ import annotations

import pytest

from src.agents.interpreter import InterpreterAgent


# `complete` = expected is_complete gate. When False, a non-empty
# question is also required.
CASES: list[dict] = [
    {
        "id": "complete_cube_full_dims",
        "description": "ein wuerfel 50x50x50 mm",
        "complete": True,
        "covers": "Alle drei Masse genannt → durchwinken, keine Rueckfrage",
    },
    {
        "id": "complete_plate_full_dims",
        "description": "eine platte 120x80x15 mm aus aluminium",
        "complete": True,
        "covers": "Platte voll bemasst (Material ist kein kritisches Mass)",
    },
    {
        "id": "complete_cube_with_feature",
        "description": "ein wuerfel 60x60x60 mit einer zentralen bohrung 10mm durchgehend",
        "complete": True,
        "covers": "Voll bemasstes Teil + Feature → komplett",
    },
    {
        "id": "incomplete_box_no_dims",
        "description": "eine kiste",
        "complete": False,
        "covers": "Kein einziges Mass → kritische Dimension fehlt, Rueckfrage",
    },
    {
        "id": "incomplete_plate_missing_thickness",
        "description": "eine platte 100x100",
        "complete": False,
        "covers": "Dicke fehlt → Rueckfrage nach dem dritten Mass",
    },
]


@pytest.fixture(scope="module")
def interpreter() -> InterpreterAgent:
    return InterpreterAgent()


@pytest.mark.agent_regression
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_interpreter_case(interpreter: InterpreterAgent, case: dict) -> None:
    state = {"description": case["description"], "specification": "", "messages": []}
    result = interpreter.process(state)

    is_complete = bool(result.get("is_complete"))
    question = (result.get("question") or "").strip()

    problems: list[str] = []
    if is_complete != case["complete"]:
        problems.append(
            f"is_complete: got {is_complete}, expected {case['complete']}"
        )
    if not case["complete"] and is_complete is False and not question:
        problems.append("incomplete case must carry a non-empty question")

    if problems:
        raise AssertionError(
            f"\n  case: {case['id']}"
            f"\n  result: {result}"
            f"\n  → {' | '.join(problems)}"
        )
