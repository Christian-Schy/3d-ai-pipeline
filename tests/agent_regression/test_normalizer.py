"""
tests/agent_regression/test_normalizer.py — live regression cases for
NormalizerAgent.normalize().

After specialization (Positionierungs-Vokabular raus aus prompt_normalizer.py),
the Normalizer's job is:

  - typ refinement   (bohrung → lochkreis/eckbohrungen/bohrungsreihe)
  - richtung         (slot/line axis)
  - position keyword (zentriert / von_kanten / ...)
  - sizes            (laenge, breite, tiefe, durchmesser, drehung)
  - notes            (free text)

The Normalizer must NOT emit per-direction positioning params anymore —
that's exclusively the classifier's job. The `assert_no_doppelarbeit`
guard below catches any `abstand_<dir>/versatz_<dir>/kante_<dir>/
anfang_<dir>/ende_<dir>` leak in the parameter dict.

Pattern-specific keys like `abstand_kante` (eckbohrungen corner→hole
distance, no direction suffix) and `abstand` (bohrungsreihe spacing)
are NOT positioning — they describe the pattern itself.
"""

from __future__ import annotations

import pytest

from src.agents.normalizer_agent import NormalizerAgent

from tests.agent_regression._lib import POSITIONING_KEYS


# Each case asserts on three layers:
#   typ            (exact match if specified)
#   richtung       (exact match if specified — empty string allowed for non-slot/line typs)
#   parameter_must (subset: these keys must be present with these values)
#
# All cases also enforce: parameter contains NO per-direction positioning
# keys. That's the doppelarbeit guard — see assert_no_doppelarbeit below.
CASES: list[dict] = [
    # ── Type-Refinement / clean output (sollten immer passen) ─────────────
    {
        "id": "tasche_simple_zentriert",
        "phrase": "oben eine zentrierte tasche 50x30x8",
        "seite": "oben",
        "expected": {
            "typ": "tasche",
            "parameter_must": {"laenge": 50, "breite": 30, "tiefe": 8},
        },
    },
    {
        "id": "tasche_with_rotation",
        "phrase": "oben eine zentrierte tasche 25x18x10 um 20 grad gedreht",
        "seite": "oben",
        "expected": {
            "typ": "tasche",
            "parameter_must": {"laenge": 25, "breite": 18, "tiefe": 10, "drehung": 20},
        },
    },
    {
        "id": "nut_simple_richtung_x",
        "phrase": "oben eine nut 5x5 entlang x-achse laenge 40mm",
        "seite": "oben",
        "expected": {
            "typ": "nut",
            "richtung": "x",
            "parameter_must": {"breite": 5, "tiefe": 5, "laenge": 40},
        },
    },
    {
        "id": "bohrung_simple",
        "phrase": "oben eine 8mm bohrung 12 tief",
        "seite": "oben",
        "expected": {
            "typ": "bohrung",
            "parameter_must": {"durchmesser": 8, "tiefe": 12},
        },
    },
    {
        "id": "lochkreis_refinement",
        "phrase": "oben ein lochkreis aus 6 bohrungen 5mm 8 tief auf teilkreis 40mm",
        "seite": "oben",
        "expected": {
            "typ": "lochkreis",
            # Pattern-Konvention: Loch-Groesse heisst bohr_durchmesser (nicht durchmesser).
            "parameter_must": {"anzahl": 6, "bohr_durchmesser": 5},
        },
    },
    {
        "id": "eckbohrungen_refinement",
        "phrase": "oben 4 bohrungen 5mm 8 tief an jeder ecke randabstand 10mm",
        "seite": "oben",
        "expected": {
            "typ": "eckbohrungen",
            "parameter_must": {"anzahl": 4, "bohr_durchmesser": 5},
            # abstand_kante (no direction suffix) ist Pattern-Param, KEIN positioning
        },
    },
    {
        "id": "bohrungsreihe_refinement",
        "phrase": "oben eine bohrungsreihe aus 4 bohrungen 5mm 6 tief entlang x-achse",
        "seite": "oben",
        "expected": {
            "typ": "bohrungsreihe",
            "richtung": "x",
            "parameter_must": {"anzahl": 4, "bohr_durchmesser": 5},
        },
    },

    # ── Doppelarbeit-Wache (sollte NACH Spezialisierung passen) ──────────
    {
        "id": "guard_tasche_abstand_phrase",
        "phrase": "oben eine tasche 30x20x10 von linker kante 15mm und von vorderer kante 25mm",
        "seite": "oben",
        "expected": {
            "typ": "tasche",
            "parameter_must": {"laenge": 30, "breite": 20, "tiefe": 10},
            # KEINE abstand_links, abstand_vorne — Klassifizierer-Aufgabe
        },
    },
    {
        "id": "guard_tasche_taschen_kante_phrase",
        "phrase": "vorne eine tasche 25x18x8 die linke taschen-kante 12mm vom linken rand und die untere taschen-kante 15mm vom unteren rand",
        "seite": "vorne",
        "expected": {
            "typ": "tasche",
            "parameter_must": {"laenge": 25, "breite": 18, "tiefe": 8},
            # KEINE kante_links, kante_unten
        },
    },
    {
        "id": "guard_tasche_corner_phrase",
        "phrase": "unten eine tasche 25x18x6 in der oberen rechten ecke 22mm nach links und 18mm nach unten versetzt",
        "seite": "unten",
        "expected": {
            "typ": "tasche",
            "parameter_must": {"laenge": 25, "breite": 18, "tiefe": 6},
            # KEINE abstand_rechts/abstand_oben — Klassifizierer kann das jetzt korrekt
        },
    },
    {
        "id": "guard_tasche_versatz_aus_mitte",
        "phrase": "unten eine tasche 30x25x6 von der mitte um 10mm nach rechts und 15mm nach hinten versetzt",
        "seite": "unten",
        "expected": {
            "typ": "tasche",
            "parameter_must": {"laenge": 30, "breite": 25, "tiefe": 6},
            # KEINE versatz_rechts/versatz_hinten — Klassifizierer-Aufgabe
        },
    },
    {
        "id": "guard_tasche_buendig",
        "phrase": "vorne eine tasche 25x18x8 oben buendig anliegend und 20mm von der rechten kante",
        "seite": "vorne",
        "expected": {
            "typ": "tasche",
            "parameter_must": {"laenge": 25, "breite": 18, "tiefe": 8},
            # KEINE kante_oben:0 / abstand_rechts:20
        },
    },
    {
        "id": "guard_nut_abstand_phrase",
        "phrase": "oben eine nut 5x5 entlang x-achse laenge 50mm von rechter kante 30mm",
        "seite": "oben",
        "expected": {
            "typ": "nut",
            "richtung": "x",
            "parameter_must": {"breite": 5, "tiefe": 5, "laenge": 50},
            # KEINE abstand_rechts
        },
    },
    {
        "id": "guard_nut_endpoints",
        "phrase": "oben eine nut 5x3 anfangspunkt 20mm von linker kante endpunkt 80mm von linker kante",
        "seite": "oben",
        "expected": {
            "typ": "nut",
            "parameter_must": {"breite": 5, "tiefe": 3},
            # KEINE anfang_links/ende_links — feature_builder._resolve_slot_endpoints
            # rechnet aus den Klassifizierer-Hints
        },
    },
    {
        "id": "guard_bohrung_abstand_phrase",
        "phrase": "oben eine 8mm bohrung 12 tief von linker kante 25mm und von vorderer kante 30mm",
        "seite": "oben",
        "expected": {
            "typ": "bohrung",
            "parameter_must": {"durchmesser": 8, "tiefe": 12},
            # KEINE abstand_links/abstand_vorne
        },
    },
    {
        "id": "guard_pattern_lochkreis_corner_anchor",
        "phrase": "links ein kreismuster aus 4 bohrungen 4mm 8 tief auf teilkreis 20mm in der oberen rechten ecke 15mm nach links und 15mm nach unten versetzt",
        "seite": "links",
        "expected": {
            "typ": "lochkreis",
            "parameter_must": {"anzahl": 4, "bohr_durchmesser": 4},
            # KEINE abstand_*/versatz_* — Eck-Versatz ist Klassifizierer-Job
        },
    },
]


def assert_no_doppelarbeit(parameter: dict, case_id: str) -> None:
    """Raise if `parameter` contains any per-direction positioning key.

    After specialization the Normalizer must not emit `abstand_<dir>/
    versatz_<dir>/kante_<dir>/anfang_<dir>/ende_<dir>` — those are the
    classifier's authority. Pattern keys without direction suffix
    (`abstand_kante`, `abstand`) are allowed.
    """
    leaked = {k: v for k, v in parameter.items() if k in POSITIONING_KEYS}
    if leaked:
        raise AssertionError(
            f"\n  case: {case_id}"
            f"\n  Doppelarbeit-Leak — Normalizer emittiert Positionierungs-Keys"
            f" (Klassifizierer-Aufgabe!): {leaked}"
        )


@pytest.fixture(scope="module")
def normalizer() -> NormalizerAgent:
    return NormalizerAgent()


@pytest.mark.agent_regression
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_normalizer_case(normalizer: NormalizerAgent, case: dict) -> None:
    phrase = case["phrase"]
    seite = case["seite"]
    result = normalizer.normalize(phrase, seite, phrase)

    expected = case["expected"]
    problems: list[str] = []

    # typ + richtung exact
    for key in ("typ", "richtung"):
        if key in expected and result.get(key) != expected[key]:
            problems.append(f"{key}: got {result.get(key)!r}, expected {expected[key]!r}")

    # required parameter subset
    actual_params = result.get("parameter") or {}
    for k, v in expected.get("parameter_must", {}).items():
        if actual_params.get(k) != v:
            problems.append(f"parameter.{k}: got {actual_params.get(k)!r}, expected {v!r}")

    if problems:
        raise AssertionError(
            f"\n  case: {case['id']}"
            f"\n  result: {result}"
            f"\n  → {' | '.join(problems)}"
        )

    # Doppelarbeit-Wache (immer aktiv, fuer ALLE Cases)
    assert_no_doppelarbeit(actual_params, case["id"])
