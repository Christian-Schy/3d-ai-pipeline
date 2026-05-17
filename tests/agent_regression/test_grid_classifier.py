"""
tests/agent_regression/test_grid_classifier.py — live regression cases
for the grid_classifier sub-agent (ADR 0009).

What this catches that the unit-tests + pipeline heatmap don't:
- The core Raster-vs-Eckbohrungen split (ADR 0014 §1, V2 bug class): a
  phrase with a *Rasterabstand* must emit rows/cols/rasterabstand; a
  phrase with only a *Randabstand* must emit anzahl/abstand_kante and
  NEVER rows/cols. Each case forbids the opposing family's keys.
- "2x2 Lochmuster" WITHOUT a Rasterabstand → 4 Eckbohrungen, not a 2×2
  Raster — the single most error-prone wording.
- per-axis Rasterabstand (rasterabstand_x / rasterabstand_y).

Run: `pytest tests/agent_regression -m agent_regression -v` (needs Ollama).
"""

from __future__ import annotations

import pytest

from src.agents.classifier_sub_agents import GridClassifier

from tests.agent_regression._lib import assert_hints, default_box


# `expected` = hint subset asserted exactly. `forbidden` = keys that must
# be absent — this is the family-misclassification guard.
CASES: list[dict] = [
    # ── Explizites RASTER — Rasterabstand genannt → rows/cols ───────────
    {
        "id": "01_raster_4x3_rasterabstand",
        "phrase": "oben ein lochmuster 4x3 aus bohrungen 5mm 8 tief rasterabstand 25mm",
        "expected": {"rows": 4, "cols": 3, "rasterabstand": 25},
        "forbidden": ("anzahl", "abstand_kante"),
        "covers": "M_coverage; explizites Raster — erste Zahl rows, zweite cols",
    },
    {
        "id": "02_raster_3x3_lochabstand_wording",
        "phrase": "oben ein raster 3x3 aus bohrungen 6mm 10 tief mit 30mm lochabstand",
        "expected": {"rows": 3, "cols": 3, "rasterabstand": 30},
        "forbidden": ("anzahl", "abstand_kante"),
        "covers": "'Lochabstand' ist ein Rasterabstand-Synonym → rows/cols",
    },
    {
        "id": "03_raster_per_axis_spacing",
        "phrase": "oben ein lochmuster 4x2 aus bohrungen 5mm 8 tief rasterabstand 20mm in x und 30mm in y",
        "expected": {"rows": 4, "cols": 2, "rasterabstand_x": 20, "rasterabstand_y": 30},
        "forbidden": ("anzahl", "abstand_kante"),
        "covers": "M_coverage; per-Achse Rasterabstand → rasterabstand_x/_y",
    },

    # ── ECKBOHRUNGEN — Randabstand, kein Rasterabstand → anzahl/abstand_kante ─
    {
        "id": "04_eckbohrungen_jede_ecke",
        "phrase": "oben 4 bohrungen 5mm 8 tief an jeder ecke randabstand 10mm",
        "expected": {"anzahl": 4, "abstand_kante": 10},
        "forbidden": ("rows", "cols", "rasterabstand"),
        "covers": "EF/NEST; 'an jeder Ecke' + Randabstand → Eckbohrungen, NIE rows/cols",
    },
    {
        "id": "05_eckbohrungen_2x2_no_rasterabstand",
        "phrase": "oben ein 2x2 lochmuster aus bohrungen 6mm 8 tief randabstand 12mm zur kante",
        "expected": {"anzahl": 4, "abstand_kante": 12},
        "forbidden": ("rows", "cols", "rasterabstand"),
        "covers": "ADR 0014 §1 V2-Bug; '2x2 Lochmuster' OHNE Rasterabstand = 4 Eckbohrungen",
    },
    {
        "id": "06_eckbohrungen_von_den_kanten",
        "phrase": "oben 4 bohrungen 5mm durchgehend jeweils 15mm von den kanten entfernt",
        "expected": {"anzahl": 4, "abstand_kante": 15},
        "forbidden": ("rows", "cols", "rasterabstand"),
        "covers": "'von den Kanten entfernt' Wording → Eckbohrungen",
    },
]


@pytest.fixture(scope="module")
def grid_classifier() -> GridClassifier:
    return GridClassifier()


# W3 (ADR 0014): grid_classifier emittiert direkt typ=eckbohrungen
# (deckt Raster UND Eckbohrungen-Arm ab — beide laufen auf hole_pattern_grid).
_EXPECTED_TYP = "eckbohrungen"


@pytest.mark.agent_regression
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_grid_classifier_case(grid_classifier: GridClassifier, case: dict) -> None:
    res = grid_classifier.classify(
        {"phrase": case["phrase"], "teil_id": "wuerfel", "phrase_idx": 0},
        default_box(),
    )
    if res.get("typ") != _EXPECTED_TYP:
        raise AssertionError(
            f"\n  case: {case['id']}"
            f"\n  typ: got {res.get('typ')!r}, expected {_EXPECTED_TYP!r}"
            f"\n  result: {res}"
        )
    assert_hints(
        res.get("parameter_hints", {}),
        case["expected"],
        case["id"],
        forbidden=tuple(case.get("forbidden", ())),
    )
