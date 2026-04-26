"""
scripts/build_goldens.py — Erzeugt Golden-Test-Cases aus kuratierten Traces.

Workflow:
    .venv/bin/python scripts/build_goldens.py
    .venv/bin/pytest tests/golden/ -v

Jeder Case besteht aus:
    tests/golden/<slug>/spec.txt                — trace["specification"]
    tests/golden/<slug>/expected_blueprint.json — resolve_blueprint(trace["blueprint"])
    tests/golden/<slug>/notes.md                — Trace-ID + Test-Zweck

Resolver ist deterministisch — kein LLM nötig.
"""

from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "data" / "dspy_training"))

from src.tools.blueprint_resolver import resolve_blueprint
from sonnet_traces import TRACES as SONNET_TRACES

# reference_traces ebenfalls einbeziehen
try:
    from reference_traces import TRACES as REF_TRACES
except Exception:
    REF_TRACES = []

ALL_TRACES = {t["id"]: t for t in REF_TRACES + SONNET_TRACES}

GOLDEN_ROOT = Path(__file__).parent.parent / "tests" / "golden"

# ── Kuratierte Auswahl ───────────────────────────────────────────
# Format: (trace_id, slug, test_zweck)
SELECTION = [
    (
        "t27_platte_hochkant_oben_p2_bohrung_ta",
        "platte_hochkant_p2_bohrung",
        "hochkant-Orientation-Swap: Y/Z getauscht, Bohrung auf neuer Oberseite (120x15), P2 Eck-Abstand",
    ),
    (
        "t44_platte_wuerfel_ueberstand_ta",
        "platte_wuerfel_p4_ueberstand_rechts",
        "P4 Ueberstand: Wuerfel steht 15mm rechts ueber Platte hinaus — overhang-Offset-Berechnung",
    ),
    (
        "t45_3teile_kette_umg",
        "3teile_kette_p3",
        "3-Teil-Kette: platte → wuerfel(rechts) → platte_klein(oben) — parent-chain resolver",
    ),
    (
        "t59_wuerfel_platte_p5_anchor_oben_links_umg",
        "wuerfel_platte_p5_anchor_oben_links",
        "P5 Anker: obere linke Ecke der Platte liegt auf linker Kante des Wuerfels — _apply_anchor",
    ),
    (
        "t62_wuerfel_platte_p5_winkel_45ccw_knapp",
        "wuerfel_platte_p5_winkel_45ccw",
        "P5 + Winkel: Anker + pre_rotation -45deg (CCW) — kombinierter Anchor+Rotation-Pfad",
    ),
    (
        "t63_quader_kleiner_wuerfel_p5_mitte_ecke_30cw_umg",
        "quader_wuerfel_p5_winkel_30cw",
        "P5 + Winkel CW: mittelpunkt-auf-ecke + 30deg CW Rotation vor dem Anchoring",
    ),
    (
        "t64_3teil_kette_p3_p5_tech",
        "3teile_kette_p3_p5",
        "3-Teil-Kette mit P5-Anker: Basis → Stueck(P3) → Lasche(P5) — parent-chain + anchor kombiniert",
    ),
    (
        "t67_zylinder_3features_stirnseiten_umg",
        "zylinder_3feat_stirnseiten",
        "Zylinder Stirnseite oben+unten, multi-feature: 2 Bohrungen + 1 Tasche — Stirnflächen-Mapping",
    ),
    (
        "t68_wuerfel_5features_eckbohrungen_zentral_knapp",
        "wuerfel_5feat_eckbohrungen_zentral",
        "5 Features: zentrale Bohrung P0 + 4 Eckbohrungen P2 — symmetrische Offset-Berechnung",
    ),
    (
        "t82_platte_5features_ecken_fase_radius_nut_tech",
        "platte_5feat_ecken_fase_radius_nut",
        "5 Features Mix: Eckbohrungen + Fase + Fillet + Nut — chamfer/fillet/slot Typ-Abdeckung",
    ),
    (
        "t84_2teile_p5_mit_features_knapp",
        "2teile_p5_mit_features",
        "P5 + Features auf beiden Teilen: Anker-Platzierung UND Feature-Subtraktionen",
    ),
    (
        "t85_2teile_p4_bündig_oben_features_tech",
        "2teile_p4_flush_top_mit_features",
        "P4 flush_top + Features: Ausrichtung oberkante + Bohrung/Tasche auf Kind-Teil",
    ),
    (
        "t107_platte_hochkant_4features_umg",
        "platte_hochkant_4feat",
        "hochkant + 4 Multi-Feature: Y/Z-Swap + mehrere Bohrungen auf verschiedenen Flaechen",
    ),
]


def build_golden(trace_id: str, slug: str, zweck: str) -> bool:
    trace = ALL_TRACES.get(trace_id)
    if not trace:
        print(f"  SKIP  {slug}: Trace '{trace_id}' nicht gefunden")
        return False

    case_dir = GOLDEN_ROOT / slug
    case_dir.mkdir(parents=True, exist_ok=True)

    # spec.txt
    (case_dir / "spec.txt").write_text(
        trace["specification"], encoding="utf-8"
    )

    # expected_blueprint.json via deterministischen Resolver
    try:
        resolved = resolve_blueprint(trace["blueprint"])
    except Exception as e:
        print(f"  ERROR {slug}: resolve_blueprint fehlgeschlagen: {e}")
        return False

    (case_dir / "expected_blueprint.json").write_text(
        json.dumps(resolved, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # notes.md
    meta = trace.get("metadata", {})
    assertions = trace.get("assertions", {})
    notes = f"""# Golden Case: {slug}

**Quelle:** Trace `{trace_id}` aus sonnet_traces.py
**Difficulty:** {meta.get('difficulty', '?')}
**Category:** {meta.get('category', '?')}
**Sprachstil:** {meta.get('sprachstil', '?')}

## Was wird hier getestet?

{zweck}

## Assertions aus Trace

```json
{json.dumps(assertions, ensure_ascii=False, indent=2)}
```

## Bekannte Risiken

<!-- Eintragen wenn der Test rot wird -->
"""
    (case_dir / "notes.md").write_text(notes, encoding="utf-8")

    n_feats = len(resolved.get("features", {}))
    print(f"  OK    {slug}  ({n_feats} features)")
    return True


def main():
    print(f"\nErzeuge {len(SELECTION)} Golden-Test-Cases in {GOLDEN_ROOT}\n")
    ok = 0
    for trace_id, slug, zweck in SELECTION:
        if build_golden(trace_id, slug, zweck):
            ok += 1

    print(f"\n{ok}/{len(SELECTION)} Golden-Cases erzeugt.")
    if ok < len(SELECTION):
        print("Fehlende Traces pruefen!")


if __name__ == "__main__":
    main()
