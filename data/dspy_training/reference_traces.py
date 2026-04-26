"""
reference_traces.py — 3 Referenz-Beispiele im neuen Trace-Format.

Diese Datei ist die **Vorlage fuer Sonnet** (und andere LLMs, die Beispiele
generieren). Sie zeigt, wie ein vollstaendiger Pipeline-Trace aussieht,
inkl. aller Agent-Ground-Truths.

Neue Traces werden in `TRACES` angehaengt. Am Ende exportiert das Script
`traces.json` fuer Inspektion und gibt die Anzahl aus. Fuer das eigentliche
Training muessen die Traces noch mit den Legacy-Beispielen gemerged werden —
siehe SONNET_PLAN.md.
"""

from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agent_contracts import (
    project_traces, validate_all, coverage_report, CONTRACTS
)


# ══════════════════════════════════════════════════════════════════
# Helper — einheitliche Position-Struktur (semantic)
# ══════════════════════════════════════════════════════════════════

def _pos(side="oben", alignment="centered", edge_distances=None,
         angle_deg=0, notes=""):
    """Semantic position — Feature auf einer Face eines Teils."""
    return {
        "side": side,
        "alignment": alignment,
        "edge_distances": edge_distances,
        "angle_deg": angle_deg,
        "notes": notes,
    }


def _norm(parent, seite, ausrichtung="centered", orientierung="standard",
          anliegende_flaeche=None, abstand=None, winkel=0,
          anker=None, pre_rotation=None, notes=""):
    """Normalized Teil-Placement (Output von PositionNormalizer)."""
    return {
        "parent": parent,
        "seite": seite,
        "ausrichtung": ausrichtung,
        "orientierung": orientierung,
        "anliegende_flaeche": anliegende_flaeche,
        "abstand": abstand,
        "winkel": winkel,
        "anker": anker,
        "pre_rotation": pre_rotation,
        "notes": notes,
    }


TRACES: list[dict] = []


# ══════════════════════════════════════════════════════════════════
# TRACE A — Single-Part, 1 Feature, P0 zentral
# Einfachster Fall: kein PositionExtractor, kein PositionNormalizer,
# Assembly trivial. Deckt nur inventar + teil_definierer.
# ══════════════════════════════════════════════════════════════════

TRACES.append({
    "id": "ref_A_wuerfel_bohrung_zentral",
    "specification": "50mm Wuerfel mit einer Bohrung Ø10 oben zentral, durchgehend",
    "metadata": {
        "difficulty": "P0",
        "category": "single_part_single_feature",
        "sprachstil": "knapp_technisch",
        "matrix_cell": "FORM=wuerfel, FACE=oben, POSITION=P0",
    },

    # — Agent: inventar —
    "inventar": {
        "teil_count": 1,
        "teile": [
            {"id": "wuerfel", "type": "box", "beschreibung": "50mm Wuerfel",
             "raw_params": {"x": 50, "y": 50, "z": 50}},
        ],
        "aktionen": [
            {"teil_id": "wuerfel", "seite": "oben",
             "beschreibung": "Bohrung Ø10 zentral, durchgehend"},
        ],
    },

    # — Agent: position_extractor —
    # NICHT noetig bei single-part (Adapter skipped).

    # — Agent: position_normalizer —
    # NICHT noetig bei single-part.

    # — Agent: teil_definierer —
    "teil_definitionen": [{
        "id": "wuerfel", "type": "box",
        "params": {"x": 50, "y": 50, "z": 50},
        "orientation": "standard",
        "features": [
            {"id": "bohrung_zentral", "type": "hole_single",
             "params": {"diameter": 10, "depth": 50},  # durchgehend bei 50er Wuerfel
             "position": _pos("oben"),
             "operation": "subtract"},
        ],
    }],

    # — Agent: assembly (bzw. monolithic BA) —
    "blueprint": {
        "description": "50mm Wuerfel mit zentraler Bohrung Ø10 oben durchgehend",
        "build_order": ["wuerfel", "bohrung_zentral"],
        "features": {
            "wuerfel": {"type": "box", "params": {"x": 50, "y": 50, "z": 50},
                        "orientation": "standard", "parent": None,
                        "operation": "add", "notes": ""},
            "bohrung_zentral": {"type": "hole_single",
                                "params": {"diameter": 10, "depth": 50},
                                "parent": "wuerfel", "position": _pos("oben"),
                                "operation": "subtract", "notes": ""},
        },
    },

    # — Phase B Assertions (deterministisch) —
    "assertions": {
        "expected_volume_approx": 50**3 - 3.14159 * 5**2 * 50,  # Wuerfel - Zylinder
        "expected_bbox": [50, 50, 50],
        "expected_feature_count": {"box": 1, "hole_single": 1},
    },
})


# ══════════════════════════════════════════════════════════════════
# TRACE B — Single-Part, Multi-Feature, gemischt P0 und P2
# Deckt: mehrere Features auf einem Teil, Edge-Distances (P2).
# ══════════════════════════════════════════════════════════════════

TRACES.append({
    "id": "ref_B_platte_5_bohrungen",
    "specification": (
        "100x100x20 Platte. Oben eine zentrale Bohrung Ø20 durchgehend. "
        "Zusaetzlich 4 Bohrungen Ø8 durchgehend, je 15mm von den Eck-Kanten entfernt."
    ),
    "metadata": {
        "difficulty": "P2",
        "category": "single_part_multi_feature",
        "sprachstil": "technisch_ausfuehrlich",
        "matrix_cell": "FORM=platte, FACE=oben, POSITION=P0+P2, ANZAHL=1+4",
    },

    "inventar": {
        "teil_count": 1,
        "teile": [
            {"id": "platte", "type": "box", "beschreibung": "100x100x20 Platte",
             "raw_params": {"x": 100, "y": 100, "z": 20}},
        ],
        "aktionen": [
            {"teil_id": "platte", "seite": "oben",
             "beschreibung": "zentrale Bohrung Ø20 durchgehend"},
            {"teil_id": "platte", "seite": "oben",
             "beschreibung": "4 Bohrungen Ø8 durchgehend, je 15mm von den Eck-Kanten"},
        ],
    },

    "teil_definitionen": [{
        "id": "platte", "type": "box",
        "params": {"x": 100, "y": 100, "z": 20},
        "orientation": "standard",
        "features": [
            {"id": "bohrung_zentral", "type": "hole_single",
             "params": {"diameter": 20, "depth": 20},
             "position": _pos("oben"),
             "operation": "subtract"},
            {"id": "bohrungen_ecken", "type": "hole_pattern",
             "params": {"diameter": 8, "depth": 20, "count_x": 2, "count_y": 2,
                        "spacing_x": 70, "spacing_y": 70},  # 100 - 2*15 = 70
             "position": _pos("oben", edge_distances={
                 "left": 15, "right": 15, "front": 15, "back": 15
             }),
             "operation": "subtract"},
        ],
    }],

    "blueprint": {
        "description": "100x100x20 Platte mit zentraler Bohrung + 4 Eck-Bohrungen oben",
        "build_order": ["platte", "bohrung_zentral", "bohrungen_ecken"],
        "features": {
            "platte": {"type": "box", "params": {"x": 100, "y": 100, "z": 20},
                       "orientation": "standard", "parent": None,
                       "operation": "add", "notes": ""},
            "bohrung_zentral": {"type": "hole_single",
                                "params": {"diameter": 20, "depth": 20},
                                "parent": "platte", "position": _pos("oben"),
                                "operation": "subtract", "notes": ""},
            "bohrungen_ecken": {"type": "hole_pattern",
                                "params": {"diameter": 8, "depth": 20,
                                           "count_x": 2, "count_y": 2,
                                           "spacing_x": 70, "spacing_y": 70},
                                "parent": "platte",
                                "position": _pos("oben", edge_distances={
                                    "left": 15, "right": 15, "front": 15, "back": 15
                                }),
                                "operation": "subtract", "notes": ""},
        },
    },

    "assertions": {
        "expected_bbox": [100, 100, 20],
        "expected_feature_count": {"box": 1, "hole_single": 1, "hole_pattern": 1},
    },
})


# ══════════════════════════════════════════════════════════════════
# TRACE C — Multi-Part, P3 einfache Platzierung
# Deckt: PositionExtractor, PositionNormalizer, Assembly mit parent/child.
# ══════════════════════════════════════════════════════════════════

TRACES.append({
    "id": "ref_C_wuerfel_platte_rechts",
    "specification": "Wuerfel 50mm. Rechts daneben eine Platte 40x40x20 zentriert.",
    "metadata": {
        "difficulty": "P3",
        "category": "multi_part_simple",
        "sprachstil": "knapp_technisch",
        "matrix_cell": "FORM=wuerfel+platte, POSITION=P3(rechts centered)",
    },

    "inventar": {
        "teil_count": 2,
        "teile": [
            {"id": "wuerfel", "type": "box", "beschreibung": "50mm Wuerfel",
             "raw_params": {"x": 50, "y": 50, "z": 50}},
            {"id": "platte", "type": "box", "beschreibung": "40x40x20 Platte",
             "raw_params": {"x": 40, "y": 40, "z": 20}},
        ],
        "aktionen": [],  # keine Features auf den Teilen
    },

    # — Agent: position_extractor — (nur fuer kind-teile, root ueberspringen)
    "position_extractor": {
        "positionen": [
            {"teil_id": "platte", "parent_hint": "wuerfel",
             "beschreibung": "rechts daneben, zentriert"},
        ],
    },

    # — Agent: position_normalizer — (pro kind-teil ein Eintrag)
    "position_normalizer": [
        {
            "teil_id": "platte",
            "input_sentence": "rechts daneben, zentriert",
            "output": _norm(
                parent="wuerfel",
                seite="rechts",
                ausrichtung="centered",
                orientierung="standard",
                anliegende_flaeche="40x20",  # Kontaktflaeche Platte zum Wuerfel
            ),
        },
    ],

    "teil_definitionen": [
        {"id": "wuerfel", "type": "box",
         "params": {"x": 50, "y": 50, "z": 50},
         "orientation": "standard", "features": []},
        {"id": "platte", "type": "box",
         "params": {"x": 40, "y": 40, "z": 20},
         "orientation": "standard", "features": []},
    ],

    "blueprint": {
        "description": "50mm Wuerfel, rechts zentrierte Platte 40x40x20",
        "build_order": ["wuerfel", "platte"],
        "features": {
            "wuerfel": {"type": "box",
                        "params": {"x": 50, "y": 50, "z": 50},
                        "orientation": "standard", "parent": None,
                        "operation": "add", "notes": ""},
            "platte": {"type": "box",
                       "params": {"x": 40, "y": 40, "z": 20},
                       "orientation": "standard", "parent": "wuerfel",
                       "position": _pos("rechts", alignment="centered"),
                       "operation": "add", "notes": ""},
        },
    },

    "assertions": {
        "expected_volume_approx": 50**3 + 40*40*20,
        "expected_feature_count": {"box": 2},
    },
})


# ══════════════════════════════════════════════════════════════════
# Validate + write
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    errors = validate_all(TRACES)
    if errors:
        print("VALIDIERUNGS-FEHLER:")
        for tid, errs in errors.items():
            print(f"  [{tid}]")
            for e in errs:
                print(f"    - {e}")
        raise SystemExit(1)

    print(f"Traces: {len(TRACES)} ok")

    print("\nCoverage:")
    rep = coverage_report(TRACES)
    for k, v in rep.items():
        print(f"  {k}: {v}")

    print("\nTraining-Paare pro Agent:")
    for agent in CONTRACTS:
        pairs = project_traces(TRACES, agent)
        print(f"  {agent:<25} {len(pairs)}")

    out = Path(__file__).parent / "reference_traces.json"
    out.write_text(json.dumps(TRACES, ensure_ascii=False, indent=2))
    print(f"\nGeschrieben: {out}")
