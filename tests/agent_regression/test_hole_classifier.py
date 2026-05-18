"""
tests/agent_regression/test_hole_classifier.py — live regression cases
for the hole_classifier sub-agent.

What this catches that the unit-tests + pipeline heatmap don't:
- abstand vs versatz wording drift ("von X Kante" → abstand, "nach X
  versetzt" → versatz).
- kante_* over-emission — holes are point-like, the prompt forbids
  kante_*; this suite fails if the agent emits it anyway.
- Voice-style informal numbers + missing prepositions.

Corner rule (ADR 0014 §1): originally the corner rule lived only in
pocket_classifier. W2 moved it into the shared convention library
(`data/prompts/conventions/ecken_regel.md`), so hole_classifier now
applies it too — the `07/08_corner_*` cases passed once the fragment
was wired in and are no longer xfail.

Run: `pytest tests/agent_regression -m agent_regression -v` (needs Ollama).
"""

from __future__ import annotations

import pytest

from src.agents.classifier_sub_agents import HoleClassifier

from tests.agent_regression._lib import assert_positioning_hints, default_box


# Each case lists ONLY the positioning keys it asserts on (plus
# rotation_deg). Size keys (durchmesser/tiefe) are intentionally left out
# — see _lib.assert_positioning_hints docstring.
CASES: list[dict] = [
    # ── A1 baseline: abstand default, two directions ────────────────────
    {
        "id": "01_abstand_two_dirs_default",
        "phrase": "oben eine 8mm bohrung 12 tief von linker kante 25mm und von vorderer kante 30mm",
        "expected": {"abstand_links": 25, "abstand_vorne": 30},
        "covers": "B_coverage baseline; 'von X Kante' → abstand_* (Bohrung ist punktfoermig)",
    },
    {
        "id": "02_abstand_von_oben_rechts",
        "phrase": "vorne eine bohrung durchmesser 6 10 tief 20mm von oben und 15mm von rechts",
        "expected": {"abstand_oben": 20, "abstand_rechts": 15},
        "covers": "'von oben/rechts' ohne das Wort 'Kante' → trotzdem abstand_*",
    },

    # ── Versatz aus Mitte ───────────────────────────────────────────────
    {
        "id": "03_versatz_aus_mitte_single",
        "phrase": "oben eine 10mm bohrung 8 tief 12mm aus der mitte nach hinten versetzt",
        "expected": {"versatz_hinten": 12},
        "covers": "'aus Mitte nach X versetzt' → versatz_* (nicht abstand_*)",
    },
    {
        "id": "04_versatz_aus_mitte_double",
        "phrase": "oben eine bohrung 8mm 10 tief von der mitte 20mm nach rechts und 10mm nach vorne versetzt",
        "expected": {"versatz_rechts": 20, "versatz_vorne": 10},
        "covers": "Zwei-Achsen Versatz aus Mitte",
    },

    # ── Centered baseline (negative case: no positioning at all) ────────
    {
        "id": "05_zentriert_no_positioning",
        "phrase": "hinten eine zentrierte bohrung 12mm durchgehend",
        "expected": {},
        "covers": "zentriert → keine Positionierungs-Keys (regression catch für Over-Emission)",
    },

    # ── Voice / informal wording ────────────────────────────────────────
    {
        "id": "06_voice_informal_numbers",
        "phrase": "oben bohrung 8 durchmesser 12 tief von links 30 von vorne 20",
        "expected": {"abstand_links": 30, "abstand_vorne": 20},
        "covers": "Voice-Variante; bare Zahlen ohne 'mm', ohne 'Kante'",
    },

    # ── T08-style corner rule — via W2 convention library ───────────────
    {
        "id": "07_corner_oben_rechts",
        "phrase": "oben eine 8mm bohrung 10 tief in der oberen rechten ecke 22mm nach links und 18mm nach unten versetzt",
        "expected": {"abstand_rechts": 22, "abstand_oben": 18},
        "covers": "EF/NEST §1; Ecke oben-rechts → abstand_oben + abstand_rechts (W2 ecken_regel.md)",
    },
    {
        "id": "08_corner_unten_links",
        "phrase": "oben eine bohrung 6mm 8 tief in der unteren linken ecke 15mm nach rechts und 12mm nach oben versetzt",
        "expected": {"abstand_links": 15, "abstand_unten": 12},
        "covers": "EF/NEST §1; Ecke unten-links → abstand_unten + abstand_links (W2 ecken_regel.md)",
    },

    # ── NEST n6 Heatmap-Fail (run 7402cecb) ────────────────────────────
    # Bohrung in Tasche, Eck-Phrase OHNE explizites Seite-Wort am Anfang
    # (Seite ergibt sich aus dem Tasche-Kontext). hole_classifier emittierte
    # vor 2026-05-18 versatz_unten/links, korrekt ist abstand_rechts/oben
    # (Ecken-Regel; Bemassung Zentrum von rechter+oberer Pocket-Kante).
    {
        "id": "09_corner_in_nest_no_side_prefix",
        "phrase": "obere rechte ecke 3mm nach unten und 5mm nach links versetzt eine 4mm bohrung 3 tief",
        "expected": {"abstand_rechts": 5, "abstand_oben": 3},
        "covers": "NEST n6: Eck-Phrase ohne fuehrendes Seite-Wort (Bohrung in Tasche-Kontext) → abstand_*, nicht versatz_*",
    },
]


@pytest.fixture(scope="module")
def hole_classifier() -> HoleClassifier:
    return HoleClassifier()


def _ids(case: dict) -> str:
    return case["id"]


@pytest.mark.agent_regression
@pytest.mark.parametrize("case", CASES, ids=_ids)
def test_hole_classifier_case(hole_classifier: HoleClassifier, case: dict, request) -> None:
    if "xfail" in case:
        request.node.add_marker(pytest.mark.xfail(reason=case["xfail"], strict=False))
    res = hole_classifier.classify(
        {"phrase": case["phrase"], "teil_id": "wuerfel", "phrase_idx": 0},
        default_box(),
    )
    assert_positioning_hints(
        res.get("parameter_hints", {}),
        case["expected"],
        case["id"],
    )
