"""
klassifizierer_traces.py — Hand-kuratierte Trainings-/Regressions-Cases
fuer den aktions_klassifizierer.

Sammelt Bug-Cases aus Real-Runs (Quelle: data/sessions/runs.jsonl) plus
korrigierte expected-Outputs. Doppelt nutzbar:
  1. DSPy-Trainings-Material (jetzt noch nicht trainiert; Memory
     project_dspy_training_status_2026_05_08).
  2. Few-Shot-Quellen fuer prompt_aktions_klassifizierer.py.
  3. Spaeter: pytest-Regressions-Tests gegen mock-LLM-Antwort, sobald
     der Klassifizierer eine Test-Mock-Schnittstelle hat.

Schema pro Eintrag:
  id              — kurzer Slug
  phrase          — Aktions-Phrase (Splitter-Output)
  teil_type/params — Kontext fuer den Klassifizierer
  parent_phrase   — "(keine)" fuer top-level, sonst Parent-Phrase
  expected        — {typ, seite, parameter_hints}
  source_run      — runs.jsonl run_id (8 Zeichen) wenn aus Real-Run
  bug_pattern     — Kurzbeschreibung des Bug-Patterns

Verwendung:
  python -m data.dspy_training.klassifizierer_traces > klassifizierer_traces.json
"""
from __future__ import annotations
import json
import sys


TRACES = [
    # ── B_kombo_bohrungen_oben (run f28b958a, phrase_idx=1) ───────────────
    # Bug-Pattern: Face-zuerst. "oben soll unten rechts ..." — erste bare
    # Side ist FACE (oben), zweite/dritte Side beschreiben POSITION auf
    # der Face (unten, rechts). Klassifizierer hat seite=unten klassifiziert.
    # Plus: "von den kanten X mm entfernt" auf Bohrung (point-like) ist
    # DEFAULT abstand_*, nicht kante_*. Klassifizierer hat kante_rechts:10
    # gesetzt und kante_unten ganz vergessen.
    {
        "id": "klass_face_first_unten_rechts_b_bohrungen_idx1",
        "phrase": "oben soll unten rechts eine 18mm bohrung jeweils von den kanten 10mm entfernt mit 10mm tiefe hin",
        "teil_type": "box",
        "teil_params": {"x": 200, "y": 200, "z": 200},
        "parent_phrase": "(keine)",
        "expected": {
            "typ": "bohrung",
            "seite": "oben",
            "parameter_hints": {"durchmesser": 18, "tiefe": 10,
                                "abstand_unten": 10, "abstand_rechts": 10},
        },
        "source_run": "f28b958a",
        "bug_pattern": "face-first: erstes bare side-keyword ist Face, spaetere sind Position auf der Face",
    },

    # ── B_kombo_asym (run de64787b, phrase_idx=1) — DEFERRED ──────────────
    # Bug-Pattern: Face-Erbung vom Vorgaenger. Phrase "unten links jeweils
    # von kanten 10mm entfernt eine 18mm bohrung 10 tief" hat keine
    # Face-Voraussetzung — sie ist Teil der ueber Phrase 0 deklarierten
    # 200x100-Flaeche (oben). Klassifizierer kann das aktuell nicht
    # ableiten weil er per-Phrase aufgerufen wird ohne Vorgaenger-Kontext.
    # Architektur-Fix: parent_phrase erweitert um "previous_seite" (additiv).
    # Memory: project_klassifizierer_face_inheritance_deferred.
    {
        "id": "klass_face_inheritance_b_asym_idx1",
        "phrase": "unten links jeweils von kanten 10mm entfernt eine 18mm bohrung 10 tief",
        "teil_type": "box",
        "teil_params": {"x": 200, "y": 100, "z": 80},
        "parent_phrase": "(keine — face-inheritance vom Vorgaenger 'oben (also auf der 200x100 flaeche)')",
        "expected": {
            "typ": "bohrung",
            "seite": "oben",
            "parameter_hints": {"durchmesser": 18, "tiefe": 10,
                                "abstand_unten": 10, "abstand_links": 10},
        },
        "source_run": "de64787b",
        "bug_pattern": "face-inheritance: keine eigene Face-Decl, soll von Vorgaenger 'oben' erben (heute deferred)",
    },

    # ── B_kombo_asym (run de64787b, phrase_idx=4) — DEFERRED ──────────────
    # Bug-Pattern: "nach <side> X mm versetzt" wird als Face missverstanden.
    # "nach unten 15mm und nach links 20mm versetzt eine 12mm bohrung 8 tief"
    # — versatz_*, nicht seite. Plus Face-Erbung vom Vorgaenger 'rechts'.
    {
        "id": "klass_versatz_keyword_b_asym_idx4",
        "phrase": "nach unten 15mm und nach links 20mm versetzt eine 12mm bohrung 8 tief",
        "teil_type": "box",
        "teil_params": {"x": 200, "y": 100, "z": 80},
        "parent_phrase": "(keine — face-inheritance vom Vorgaenger 'rechts (also auf der 100x80 flaeche)')",
        "expected": {
            "typ": "bohrung",
            "seite": "rechts",
            "parameter_hints": {"durchmesser": 12, "tiefe": 8,
                                "versatz_unten": 15, "versatz_links": 20},
        },
        "source_run": "de64787b",
        "bug_pattern": "nach-X-versetzt: 'nach unten' ist Versatz-Praefix, nicht Face-Decl. Plus Face-Erbung",
    },
]


def main() -> None:
    json.dump(TRACES, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
