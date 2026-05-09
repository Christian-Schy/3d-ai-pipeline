"""
feature_definierer_traces.py — Hand-kuratierte Trainings-/Regressions-Cases
fuer den feature_definierer (NormalizerAgent.define_feature).

Sammelt Bug-Cases aus Real-Runs (Quelle: data/sessions/runs.jsonl) plus
korrigierte expected-Outputs. Doppelt nutzbar:
  1. DSPy-Trainings-Material (jetzt noch nicht trainiert).
  2. Regressions-Sentinels: jeder behobene Bug bekommt einen Eintrag
     hier, damit eine spaetere Refactor-Welle nicht erneut die selben
     Fehler einfuehrt.

Schema pro Eintrag:
  id          — kurzer Slug
  klassifikation — Eingabe vom Klassifizierer
  teil        — Inventar-Teil-Eintrag (id/type/raw_params)
  expected    — Erwarteter Output von define_feature
  source_run  — runs.jsonl run_id (8 Zeichen)
  bug_pattern — Kurzbeschreibung
  status      — "fixed" wenn der Bug deterministisch behoben wurde,
                "open" wenn noch nicht
"""
from __future__ import annotations
import json
import sys


TRACES = [
    # ── N_kombo phrase_idx=3 (run 08f46bc1) — FIXED 2026-05-09 ───────────
    # Bug-Pattern: Slot-Achsen-Konvention "entlang y-achse" → angle_deg=90
    # nicht codiert. feature_builder hat richtung nur in notes geschrieben
    # und angle_deg=0 gelassen. Heatmap-Diff: angle_deg erwartet 90, got 0.
    # Fix: feature_builder._build_feature mappt richtung=y → +90° (Code).
    {
        "id": "definierer_slot_y_axis_angle_90_n_kombo_idx3",
        "klassifikation": {
            "typ": "nut",
            "seite": "oben",
            "beschreibung": "oben eine nut 5x5 entlang y-achse laenge 40mm von oberer kante 30mm und von linker kante 20mm entfernt",
            "teil_id": "wuerfel",
            "phrase_idx": 3,
            "parent_phrase_idx": None,
            "parameter_hints": {"breite": 5, "tiefe": 5, "laenge": 40,
                                "abstand_oben": 30, "abstand_links": 20},
        },
        "teil": {"id": "wuerfel", "type": "box",
                  "raw_params": {"x": 100, "y": 100, "z": 100}},
        "expected": {
            "type": "slot",
            "params": {"width": 5, "depth": 5, "length": 40},
            "position_angle_deg": 90.0,
            "position_side": "oben",
        },
        "source_run": "08f46bc1",
        "bug_pattern": "slot 'entlang y-achse' → angle_deg=90 (deterministische Achsen→Winkel-Konvention)",
        "status": "fixed",
    },

    # ── N_kombo phrase_idx=8 (run 08f46bc1) — FIXED 2026-05-09 ───────────
    # Bug-Pattern: gleiche Achsen-Konvention bei expliziter Rotation:
    # "entlang x-achse 15 grad gegen uhrzeigersinn gedreht" → 0+15=15.
    # Klassifizierer emittiert rotation_deg=15, _merge_param_hints
    # uebersetzt zu drehung=15, feature_builder addiert auf angle_deg
    # base (0 fuer x-Achse). Bei "entlang y-achse 15 grad gedreht"
    # ergibt das 90+15=105.
    {
        "id": "definierer_slot_x_axis_with_rotation_n_kombo_idx8",
        "klassifikation": {
            "typ": "nut",
            "seite": "oben",
            "beschreibung": "oben eine nut 5x5 entlang x-achse laenge 50mm 15 grad gegen uhrzeigersinn gedreht zentral",
            "teil_id": "wuerfel",
            "phrase_idx": 8,
            "parent_phrase_idx": None,
            "parameter_hints": {"breite": 5, "tiefe": 5, "laenge": 50,
                                "rotation_deg": 15},
        },
        "teil": {"id": "wuerfel", "type": "box",
                  "raw_params": {"x": 100, "y": 100, "z": 100}},
        "expected": {
            "type": "slot",
            "params": {"width": 5, "depth": 5, "length": 50},
            "position_angle_deg": 15.0,
            "position_side": "oben",
        },
        "source_run": "08f46bc1",
        "bug_pattern": "slot 'entlang x-achse + 15 grad rotation' → angle_deg=15 (0 base + 15)",
        "status": "fixed",
    },

    # ── N_kombo phrase_idx=2 (run 08f46bc1) — OPEN ────────────────────────
    # Bug-Pattern: Slot ohne explizite laenge → durchgehend (parent-dim).
    # User-Phrase: "oben eine nut 5x5 entlang x-achse 10mm nach rechts versetzt"
    # — keine laenge. Klassifizierer emittiert keinen laenge-Hint.
    # feature_builder setzt length=None, Resolver kommt damit nicht klar.
    # Erwartung: length sollte zu parent-face-axis-dim defaulten (100 hier).
    # Fix-Optionen: Resolver fuellt None mit parent-Dim; ODER feature_builder
    # default mit Marker "durchgehend"; ODER Klassifizierer Few-Shot
    # "ohne explizite laenge → laenge=parent-Dim" (aber Klassifizierer kennt
    # parent-Dim nicht). Sauber: Resolver-Fix.
    {
        "id": "definierer_slot_durchgehend_default_n_kombo_idx2",
        "klassifikation": {
            "typ": "nut",
            "seite": "oben",
            "beschreibung": "oben eine nut 5x5 entlang x-achse 10mm nach rechts versetzt",
            "teil_id": "wuerfel",
            "phrase_idx": 2,
            "parent_phrase_idx": None,
            "parameter_hints": {"breite": 5, "tiefe": 5,
                                "versatz_rechts": 10},
        },
        "teil": {"id": "wuerfel", "type": "box",
                  "raw_params": {"x": 100, "y": 100, "z": 100}},
        "expected": {
            "type": "slot",
            "params": {"width": 5, "depth": 5, "length": 100},
            "position_angle_deg": 0.0,
            "position_side": "oben",
        },
        "source_run": "08f46bc1",
        "bug_pattern": "slot ohne laenge → durchgehend = parent-face-axis-dim. Resolver-Fix noetig",
        "status": "open",
    },

    # ── N_kombo phrase_idx=6 (run 08f46bc1) — OPEN ────────────────────────
    # Bug-Pattern: Anchor "liegt auf rechter kante" wird vom Klassifizierer
    # als kante_rechts=0 missverstanden — eigentlich ein Anchor-Marker
    # (parent_point=right_edge). Klassifizierer-Schema kennt parent_point
    # nicht; Anchors gehen ueber Normalizer (richtung/anchor-Felder).
    # Fix: erfordert Schema-Erweiterung des Klassifizierers ODER Normalizer-
    # Few-Shot fuer Anchor-Phrasen.
    {
        "id": "definierer_slot_anchor_edge_n_kombo_idx6",
        "klassifikation": {
            "typ": "nut",
            "seite": "oben",
            "beschreibung": "oben eine nut 5x5 entlang y-achse laenge 40mm liegt auf rechter kante an, 10mm nach oben versetzt",
            "teil_id": "wuerfel",
            "phrase_idx": 6,
            "parent_phrase_idx": None,
            "parameter_hints": {"breite": 5, "tiefe": 5, "laenge": 40,
                                "kante_rechts": 0},
        },
        "teil": {"id": "wuerfel", "type": "box",
                  "raw_params": {"x": 100, "y": 100, "z": 100}},
        "expected": {
            "type": "slot",
            "params": {"width": 5, "depth": 5, "length": 40},
            "position_angle_deg": 90.0,
            "position_side": "oben",
            "anchor_parent_point": "right_edge",
            "offset_oben": 10,
        },
        "source_run": "08f46bc1",
        "bug_pattern": "anchor 'liegt auf rechter kante' wird als kante_rechts=0 statt parent_point=right_edge erkannt",
        "status": "open",
    },
]


def main() -> None:
    json.dump(TRACES, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
