"""
tests/agent_regression/_lib.py — shared helpers for per-agent live regression tests.

These tests run real LLM calls against Ollama and check that each agent
emits the expected structured output for a curated bug-pattern catalogue.
Layer 0.5 between unit tests (parsing/format) and the full pipeline
heatmap (25 min, GPU-bound). Goal: catch agent-level wobble (DSPy demo
selection, prompt-demo drift) in ~5 min before it ever reaches the
heatmap.
"""

from __future__ import annotations

_DIRS = ("oben", "unten", "rechts", "links", "vorne", "hinten")
_POSITIONING_PREFIXES = (
    "abstand_", "versatz_", "kante_", "anfang_", "ende_",
)

POSITIONING_KEYS: frozenset[str] = frozenset(
    f"{prefix}{d}" for prefix in _POSITIONING_PREFIXES for d in _DIRS
)
EXTRA_TRACKED_KEYS: frozenset[str] = frozenset({"rotation_deg"})


def default_box(x: int = 120, y: int = 90, z: int = 50) -> dict:
    """Standard host part used by most pocket/slot regression cases."""
    return {"type": "box", "raw_params": {"x": x, "y": y, "z": z}}


def assert_positioning_hints(
    actual: dict,
    expected: dict,
    case_id: str,
) -> None:
    """Compare the positioning subset of `parameter_hints` exactly.

    Checked keys: every `abstand_/versatz_/kante_/anfang_/ende_<dir>` plus
    `rotation_deg`. Size keys (laenge/breite/tiefe/durchmesser) are
    intentionally ignored — this assertion is about *positioning
    convention* correctness, not extraction completeness.

    A case fails if:
    - an expected positioning key is missing or has the wrong value, OR
    - the agent emitted a positioning key the case did not expect
      (catches over-emission, e.g. `kante_links` where the case expects
      `abstand_links`).
    """
    tracked = POSITIONING_KEYS | EXTRA_TRACKED_KEYS
    actual_pos = {k: v for k, v in actual.items() if k in tracked}
    expected_pos = {k: v for k, v in expected.items() if k in tracked}

    missing = {
        k: expected_pos[k]
        for k in expected_pos
        if actual_pos.get(k) != expected_pos[k]
    }
    extra = {k: v for k, v in actual_pos.items() if k not in expected_pos}

    problems: list[str] = []
    if missing:
        problems.append(f"missing/wrong: {missing}")
    if extra:
        problems.append(f"unexpected: {extra}")

    if problems:
        raise AssertionError(
            f"\n  case:     {case_id}"
            f"\n  got:      {actual_pos}"
            f"\n  expected: {expected_pos}"
            f"\n  → {' | '.join(problems)}"
        )


def assert_hints(
    actual: dict,
    expected: dict,
    case_id: str,
    *,
    forbidden: tuple[str, ...] = (),
) -> None:
    """Generic hint-subset check for classifier `parameter_hints`.

    Unlike `assert_positioning_hints` this does NOT police over-emission of
    unlisted keys — use it for pattern-family keys (rows/cols/rasterabstand,
    anzahl/abstand_kante, kreis_durchmesser, abstand) and size keys, where
    the agent legitimately emits extra keys a given case does not assert on.

    A case fails if:
    - an expected key is missing or has the wrong value, OR
    - a `forbidden` key is present at all. `forbidden` catches family
      misclassification — e.g. a grid case forbids `rows`/`cols` to prove
      the agent emitted Eckbohrungen, not a Raster (ADR 0014 §1, V2 bug).
    """
    problems: list[str] = []
    for key, want in expected.items():
        if actual.get(key) != want:
            problems.append(f"{key}: got {actual.get(key)!r}, expected {want!r}")
    leaked = {k: actual[k] for k in forbidden if k in actual}
    if leaked:
        problems.append(f"forbidden present: {leaked}")

    if problems:
        raise AssertionError(
            f"\n  case:     {case_id}"
            f"\n  got:      {actual}"
            f"\n  expected: {expected}"
            + (f"\n  forbidden:{list(forbidden)}" if forbidden else "")
            + f"\n  → {' | '.join(problems)}"
        )
