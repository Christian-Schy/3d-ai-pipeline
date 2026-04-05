# CLAUDE.md — 3D AI Pipeline V2 (V3-Architektur aktiv)

## Aktueller Status: Anpassung & Verbesserung

Die V3-Architektur ("LLM als Textparser, Determinismus rechnet") ist implementiert.
Aktuelle Phase: **Feinabstimmung, Bugfixes, Qualitätsverbesserungen** auf Basis echter Run-Analyse.

**Fortschritt:**
- ✅ Phase 0: Template-Bibliothek (`src/codegen/`) — 100% compilierbare Blueprints
- ✅ Phase 1: FunctionDecomposer leitet direkt zum Executor wenn alle Features Standard sind
- ✅ Phase 2b: FPA + PPA sind reine Text-Parser (keine Offset-Berechnung mehr durch LLMs)
- ✅ Phase 2a: Feature Assigner Prompt vereinfacht ("nur lesen, nicht rechnen")
- ✅ Phase 5: Coder ist Layer 2 (nur komplexe Features)
- 🔄 Laufend: Run-Analyse → gezielte Fixes in Blueprint Assembler + Templates

**Bekannte offene Probleme (aus Run-Analyse):**
- Falsche Parent-Zuweisung bei Referenzen wie "auf die erste Platte" (LLM-Fehler)
- Diagonale Custom-Shape-Cuts erzeugen manchmal degenerate Polygone (Coder-Qualität)

---

## Projekt-Überblick

LangGraph-basierte Multi-Agent-Pipeline die natürlichsprachliche Beschreibungen
(deutsch) in CadQuery-3D-Modelle (STL) umwandelt. Langfristiges Ziel: kommerzielles
B2B-Produkt für die Fertigungsindustrie.

**Architektur ("3-Layer-System"):**
```
Layer 1: Standard-Features (Template/Deterministisch)  ← ~90% der Fälle
         Box, Hole, Slot, Pattern, Fillet, Chamfer, Shell, Pocket
         → 100% deterministisch, kein LLM nötig

Layer 2: Komplexe Features (LLM-Code)                  ← ~9% der Fälle
         Splines, Lofts, Sweeps, organische Formen, Custom Shapes
         → Coder generiert CadQuery-Code für Stubs

Layer 3: Vision → 3D (Zukunft)                         ← ~1%
         Bild/Skizze → Feature-Erkennung → Konstruktion
```

**Pipeline-Flow (V3):**
```
Text → Interpreter → Feature Tagger → Feature Assigner
     → Dispatcher → FPA (Feature Position Assigner)
                  → PPA (Part Position Assigner)
     → Blueprint Assembler (deterministisch: Offsets, Faces, Build-Order)
     → Planner (Review) → Validators
     → Function Decomposer →[template mode]→ Executor  (Layer 1: Coder überspringen!)
                           →[mixed/llm mode]→ Coder → Code Review → Executor
     → Geometry Checker → Validator
```

**Kernprinzip (V3):** LLMs normalisieren nur noch Text → strukturierte Daten.
Alle Berechnungen (Offsets, Face-Selektoren, Code-Generierung) passieren deterministisch.

**Modelle (aktuell):**
- qwen3.5:9b — Feature Tagger, Feature Assigner, FPA, PPA, Plan Validator, Code Review
- qwen3.5:35b — Interpreter, Planner
- qwen3-coder:30b — Coder (nur Layer 2: komplexe Features)

**Stack:** Python 3.12, LangGraph, CadQuery, Ollama, ChromaDB (RAG), Pop!_OS Linux

---

## Pipeline-Flow im Detail

### Phase 1: Sprachverarbeitung
| Agent | Modell | Aufgabe | RAG |
|-------|--------|---------|-----|
| **Interpreter** | 35b | Vollständigkeitsprüfung, Text wörtlich weiterreichen | 16_interpreter_knowledge |
| **Feature Tagger** | 9b | Features identifizieren (IDs + Typen + RAG-Tags) | 20_feature_catalog |
| **Feature Assigner** | 9b | Parent, Operation, Dimensionen — NUR aus Text lesen | 24_feature_assigner |
| **Feature Position Assigner (FPA)** | 9b | Face + axis_hint für Subtract-Features (Löcher, Nuten) | 25_position_assigner |
| **Part Position Assigner (PPA)** | 9b | Face + alignment + orientation_hint für Add-Features | 28_part_position |
| **Blueprint Assembler** | — | Deterministisch: Offsets berechnen, Faces validieren, Build-Order | — |

**Wichtig:** FPA und PPA liefern NUR face/alignment/orientation_hint — KEINE Offsets!
Blueprint Assembler berechnet alle Offsets deterministisch aus Spec + Dimensionen.

### Phase 2: Blueprint-Finalisierung
| Agent | Modell | Aufgabe |
|-------|--------|---------|
| **Planner** | 35b | Blueprint reviewen/korrigieren (Pass-Through für Standard-Features) |
| **Coordinate Validator** | — | Deterministisch: Dimensions-Plausibilität |
| **Plan Validator** | 9b | Logische Blueprint-Validierung |

### Phase 3: Code-Generierung (3-Layer)
| Agent | Modell | Wann aktiv | Aufgabe |
|-------|--------|-----------|---------|
| **Function Decomposer** | — | Immer | Klassifiziert Blueprint → generation_mode |
| **Executor** | — | generation_mode="template" | Template-Code direkt ausführen (Coder überspringen!) |
| **Coder** | 30b | generation_mode="mixed"/"llm" | Nur komplexe Stubs füllen |
| **Code Review** | 9b | Nach Coder | Anti-Pattern-Check |
| **Executor** | — | Nach Coder | Code ausführen, STL erzeugen |
| **Geometry Precheck** | — | Immer | STL-Validierung |
| **Validator** | 9b | Immer | Finale Qualitätsprüfung |

### generation_mode (neues State-Feld)
```
"template" → alle Features sind Standard → Coder wird übersprungen (Layer 1)
"mixed"    → Standard-Features als Templates + komplexe Stubs → Coder füllt Stubs
"llm"      → alle Features brauchen LLM-Code → voller Coder-Durchlauf
""         → Legacy-Flow (kein Blueprint vorhanden)
```

### Kernprinzip: Wer macht was?
- **LLMs** → Sprachverständnis (Text normalisieren: "oben links" → face=">Z", alignment="flush_left")
- **Deterministisch** → Mathe + Code (Offsets, Face-Selektoren, CadQuery-Templates)
- **NICHT:** Deterministische Band-Aids für LLM-Fehler (skaliert nicht!)

---

## `src/codegen/` — Template-System (NEU in V3)

```
src/codegen/
├── __init__.py              ← Öffentliche API: generate_template_code(), classify_blueprint()
├── templates.py             ← Ein Template pro Feature-Typ (gibt Code-Strings zurück)
├── assembler.py             ← Orchestriert Templates → komplettes Python-Script
└── feature_classifier.py   ← classify_blueprint() → "template" | "mixed" | "llm"
```

**Standard-Feature-Typen (Layer 1):**
```python
STANDARD_TYPES = {
    "box", "cylinder", "sphere",
    "hole", "hole_single", "hole_pattern_grid", "hole_pattern_circular",
    "hole_counterbore", "hole_countersink",
    "slot", "groove", "pocket_rect",
    "fillet", "chamfer", "shell",
    "extrusion_rect", "extrusion_round", "step",
    "base_plate", "base_cylinder", "base_sphere",
}
# Alles andere → Layer 2 (LLM-Coder: custom_shape_cut, loft, sweep, spline, ...)
```

**Slot-Konvention (wichtig!):**
- Gerader Slot (angle=0 oder 90) → `.rect().cutBlind()` — schneidet rand-zu-rand
- Diagonaler Slot → `.slot2D()` — hat abgerundete Enden
- angle=0: entlang X auf der Workplane; angle=90: entlang Y auf der Workplane
- Auf `>X/<X` Faces: workplane-X = globales Y → "entlang Y" → angle=0 (nicht 90!)

**Blueprint Assembler Safety-Nets (PRIMARY path, nicht Fallback):**
- `_validate_directional_faces` — korrigiert Face aus Spec-Text (z.B. "linker Seite" → "<X")
- `_compute_offsets_from_spec` — berechnet Offsets aus "10mm von rechter Kante" Patterns
- `_fix_add_part_alignment_from_spec` — korrigiert Alignment für Add-Parts
- `_extract_feature_contexts` — segmentiert Spec nach Feature-Keywords, inkl. "∅" und "durchmesser"
  - Directional Scoring: "left" in fid → +12 Score wenn "links" im Segment (maskiert Offset-Phrases)
  - Tie-Breaking: bei gleichem Score → bevorzuge späteres Segment (= später im Spec beschrieben)

---

## Kern-Prinzipien

### 1. Produktionsqualität
- Jede Änderung muss so geschrieben sein als ginge sie in Produktion
- Type Hints überall, Docstrings bei jeder öffentlichen Funktion
- Error Handling mit spezifischen Exceptions, nie bare `except:`
- Keine `from module import *` — immer explizit importieren

### 2. Stabilität vor Features
- Bestehende funktionierende Features NIEMALS durch Änderungen brechen
- Mass-Test nach jeder Änderung: `generate_code()` auf allen Blueprints aus `runs.jsonl`
- Ziel: 100% compilierbare Ausgabe (aktuell: 255/255 OK)
- Änderungen inkrementell — lieber 3 kleine Schritte als 1 riesiger Umbau

### 3. Messbare Verbesserungen
- Jede Optimierung muss durch echte Pipeline-Runs verifiziert werden
- Runs aus `data/sessions/runs.jsonl` analysieren (IDs, Traces, Code, Blueprints)
- "Gefühlt besser" reicht nicht — Erfolgsrate, Geometrie-Korrektheit, STL-Watertight

### 4. Agent-Isolation (Häppchen)
- Jeder Agent hat seine eigene Welt: eigenes RAG, eigenen Prompt, eigenes Schema
- FPA: nur face + axis_hint. PPA: nur face + alignment + orientation_hint. KEINE Offsets!
- Wenn ein Agent schlecht arbeitet: nur SEINEN Prompt/RAG ändern

### 5. LLMs für Sprache, Determinismus für Mathe
- **LLMs:** "oben links", "bündig rechts", "auf der 80x40 Seite" → strukturierte Labels
- **Determinismus:** Offset = (Parent/2 - Child/2), Templates → CadQuery-Code
- **KEINE deterministischen Band-Aids** für LLM-Fehler (skaliert nicht!)
  → Stattdessen: bessere Prompts + mehr RAG-Beispiele

---

## Code-Standards

### Python-Stil
```python
# RICHTIG:
def validate_blueprint(blueprint: dict, spec: str) -> ValidationResult:
    """Prüft den Blueprint gegen die Spezifikation."""

# FALSCH:
def validate(bp, s):
    # prüft blueprint
```

### Funktionslänge
- Einzelne Funktionen: max ~50 Zeilen → in Teilfunktionen aufteilen
- Gilt für Funktionen, NICHT für Dateien

### Imports
- Standardlib → Third-Party → Lokale Module
- Immer explizite Imports: `from os import path, listdir`
- NIEMALS Wildcard-Imports

### Konfiguration
- Alle Agent-Configs zentral in `data/prompts/agent_config.py`
- App-Level Config in `config/config.yaml`
- Keine hartkodierten Modellnamen im Agent-Code

### Logging
- Jeder Agent-Call: Start + Ende mit Input/Output-Zusammenfassung
- Strukturiertes Logging via structlog (JSON) für Analyse

---

## Architektur-Regeln

### LangGraph-Nodes
- Agent-Implementierungen in `src/agents/` (erben von `base.py`)
- Graph-Definition in `src/graph/`
- Neue Routing-Logik: `route_after_function_decomposer` entscheidet Layer 1 vs 2

### RAG-System
- RAG-Verzeichnisse strikt nach Agent getrennt:
  - `data/rag/01-15_*` → NUR für Coder (CadQuery-Patterns, Beispiele)
  - `data/rag/16_*` → NUR für Interpreter
  - `data/knowledge/rag_agents/20_*` → Feature Tagger
  - `data/knowledge/rag_agents/21_*` → Planner
  - `data/knowledge/rag_agents/22_*` → Plan Validator
  - `data/knowledge/rag_agents/23_*` → Code Review
  - `data/knowledge/rag_agents/24_*` → Feature Assigner
  - `data/knowledge/rag_agents/25_*` → Feature Position Assigner (FPA)
  - `data/knowledge/rag_agents/26_*` → Cylinder Patterns
  - `data/knowledge/rag_agents/27_*` → Shape Cutting
  - `data/knowledge/rag_agents/28_*` → Part Position Assigner (PPA)

### Prompts
- Prompt-Templates in `data/prompts/prompt_*.py`
- FPA + PPA Prompts: KEINE Formeln, KEINE Offset-Berechnung → nur Textverständnis
- Coder-Prompt: Layer 2 Rolle — nur Stubs ausfüllen, Template-Code NICHT anfassen

### Kontextqualität nach Modellgröße

**9b Modelle (FPA, PPA, Feature Assigner, Plan Validator, Code Review):**
- Max ~13 Regeln im System-Prompt — darüber werden Regeln ignoriert
- Klare Enum-Listen statt Freitext
- JSON-Schema für Output-Format immer mitgeben
- 1 konkretes Beispiel (Input → Output) reicht

**35b Modelle (Interpreter, Planner):**
- Deutlich mehr Regeln verkraftbar (~20-25)
- Können längere RAG-Kontexte sinnvoll verarbeiten
- Chain-of-Thought funktioniert

**30b Coder-Modell:**
- Code-spezialisiert — versteht CadQuery-Patterns gut
- Bekommt nur komplexe Stubs (standard Features bereits als fertiger Template-Code)
- Braucht konkrete Code-Beispiele im RAG

### Blueprint JSON Schema
- Änderungen rückwärtskompatibel (neue Felder optional mit Default)
- Neues Feld: `generation_mode` im State (nicht im Blueprint selbst)

---

## Anpassungs-Workflow (aktueller Fokus)

### Wie Probleme aus Runs analysiert werden:
1. Run-IDs aus Nutzer-Feedback oder `data/sessions/runs.jsonl` lesen
2. Pro Run auslesen: `user_input`, `blueprint.features` (inkl. placement), `code`, `agent_traces`
3. Blueprint-Placement prüfen: Sind `face`, `offset_x`, `offset_y` korrekt?
4. Generierten Code prüfen: Stimmen Dimensionen, Achsen, Richtungen?
5. Root cause identifizieren:
   - Falsche Face → FPA/PPA-Fehler oder `_validate_directional_faces` hat nicht gegriffen
   - Falsche Offsets → `_compute_offsets_from_spec` hatte keinen Context (→ `_extract_feature_contexts` prüfen)
   - Falsche Slot-Richtung → Angle/Axis-Mapping für Side-Faces prüfen
   - Falsche Template-Ausgabe → `src/codegen/templates.py` prüfen

### Mass-Test nach jeder Code-Änderung:
```python
# Alle Blueprints aus runs.jsonl durch den Template-Generator jagen
# Ziel: 0 FAIL, alle compilierbar
python3 -c "
import json
from src.codegen.assembler import generate_code
blueprints = [json.loads(l)['blueprint'] for l in open('data/sessions/runs.jsonl') if l.strip()]
blueprints = [b for b in blueprints if b and b.get('features')]
ok = sum(1 for b in blueprints if compile(generate_code(b), '<t>', 'exec') is None or True)
print(f'{ok}/{len(blueprints)} OK')
"
```

---

## Änderungs-Checkliste

### Template/Assembler-Änderungen
- [ ] Mass-Test läuft noch durch (0 FAIL)?
- [ ] Slot-Angle korrekt für die betroffene Face?
- [ ] Korrekte Parent-Dimensionen (px/py/pz) für die Face übergeben?
- [ ] Kein slot2D() für gerade Nuten (edge-to-edge)?

### Blueprint Assembler-Änderungen
- [ ] `_extract_feature_contexts` liefert korrekte Segmente für Testfälle?
- [ ] `_compute_offsets_from_spec` Pattern matched die neuen Formulierungen?
- [ ] Offset-Masking verhindert false-positive Directional-Matches?

### Prompt-Änderungen
- [ ] Regelanzahl im Rahmen? (9b ≤ 13, 35b ≤ 25)
- [ ] FPA/PPA: Kein Prompt der Offsets berechnen soll?
- [ ] Coder: Kein Prompt der Template-Code anfassen soll?
- [ ] Durch echte Pipeline-Runs verifiziert?

### Code-Änderungen
- [ ] Type Hints vollständig?
- [ ] Docstring bei öffentlichen Funktionen?
- [ ] Bestehende Pipeline-Runs brechen nicht?

---

## Test-Strategie

### Echte Pipeline-Runs sind der einzige valide Test
Unit Tests fangen Code-Bugs, aber die echten Probleme kommen von LLM-Antworten.

### Standard-Testfälle (nach jeder relevanten Änderung)
1. **Einfach:** "30mm Würfel"
2. **Subtraktiv:** "30mm Würfel mit 5x5 Nut vorne entlang X und 10mm Bohrung links"
3. **Additiv:** "100x100x20 Platte mit 20x50x40 Aufsatz rechts bündig oben"
4. **Multi-Part:** "Basis 100x100x20, Platte 20x80x40 mit Bohrung auf der 80x40 Seite"
5. **Komplex:** "Würfel 50mm mit Nut vorne 5x5 entlang X, Nut hinten entlang Y, Bohrung links von Oberkante 10mm, Bohrung rechts von oben 20mm von linker Kante 10mm"

### Was bei jedem Run im Log prüfen:
- success=true?
- generation_mode korrekt? (template/mixed/llm)
- Offsets im Blueprint korrekt? (nicht 0.0 wenn Spec Abstand nennt)
- Face korrekt? (nicht ">Z" wenn Spec "von links" sagt)
- Volume plausibel?
- watertight=true?

---

## Proaktive Verbesserungen

Wenn dir bei der Arbeit etwas auffällt, weise AKTIV darauf hin:

### Immer melden:
- Falsche Offsets/Faces in Blueprints (aus Run-Analyse)
- Template-Code der geometrisch falsch ist
- LLM-Fehler die systematisch auftreten (> 3 Runs betroffen → Prompt/RAG-Fix)
- Möglichkeiten für weitere deterministische Checks (spart LLM-Calls)

### Format für Vorschläge:
```
VERBESSERUNGSVORSCHLAG:
Was: [kurze Beschreibung]
Warum: [erwarteter Nutzen]
Aufwand: [gering/mittel/hoch]
Priorität: [sofort/bald/irgendwann]
```

---

## Langfristige Architektur

### Nächste Schritte nach Stabilisierung:
- Modell-Upgrade für FPA/PPA auf 35b wenn Fehlerrate zu hoch
- Layer 3 Vorbereitung: Vision → Feature-Liste (Bild → Skizze → CAD)
- Interpreter-Upgrade: abstrakte Konzepte ("Zahnrad") → strukturierte Beschreibung

### Wann lohnt sich ein größerer Umbau?
- Gleiche Fehlerklasse in > 30% der Runs
- Workaround erzeugt mehr Code als die richtige Lösung
- Eine Komponente > 3 Hotfixes in einer Woche

### Modell-Konfiguration:
| Agent | Modell | Alternative wenn Probleme |
|-------|--------|--------------------------|
| Interpreter | qwen3.5:35b | Bleibt, RAG verbessern |
| Feature Tagger | qwen3.5:9b | Regelbasiert (kein LLM) |
| Feature Assigner | qwen3.5:9b | RAG erweitern, 35b wenn nötig |
| FPA | qwen3.5:9b | RAG erweitern, 35b wenn Fehlerrate hoch |
| PPA | qwen3.5:9b | RAG erweitern, 35b wenn Fehlerrate hoch |
| Planner | qwen3.5:35b | Bleibt, RAG verbessern |
| Plan Validator | qwen3.5:9b | Regelbasiert (kein LLM) |
| Coder | qwen3-coder:30b | Bleibt (nur Layer 2) |
| Code Review | qwen3.5:9b | Regelbasiert + AST-Check |
| Validator | qwen3.5:9b | Regelbasiert (kein LLM) |

---

## Dateistruktur

```
3D_AI_Pipeline_V2/
├── CLAUDE_projekt_v2.md                  ← DU BIST HIER
│
├── data/
│   ├── knowledge/
│   │   ├── planner/rules/                ← Planner-Regeln (direkt injiziert)
│   │   └── rag_agents/
│   │       ├── 20_feature_catalog/       ← Feature Tagger RAG
│   │       ├── 21_planner_geometry/      ← Planner RAG
│   │       ├── 22_plan_validation/       ← Plan Validator RAG
│   │       ├── 23_code_review/           ← Code Review RAG
│   │       ├── 24_feature_assigner/      ← Feature Assigner RAG
│   │       ├── 25_position_assigner/     ← FPA RAG (face detection, axis_hint)
│   │       ├── 26_cylinder_patterns/     ← Cylinder Pattern RAG
│   │       ├── 27_shape_cutting/         ← Shape Cutting RAG
│   │       └── 28_part_position/         ← PPA RAG (alignment, orientation)
│   ├── rag/                              ← CadQuery-RAG für Coder + Interpreter
│   │   ├── 01_foundations/ ... 15_*/
│   │   └── 16_interpreter_knowledge/
│   ├── prompts/                          ← Prompt-Templates + Agent-Config
│   │   ├── prompt_interpreter.py
│   │   ├── prompt_feature_tagger.py
│   │   ├── prompt_feature_assigner.py    ← Text-Parser: nur parent/op/params
│   │   ├── prompt_feature_position_assigner.py  ← Text-Parser: nur face/axis_hint
│   │   ├── prompt_part_position_assigner.py     ← Text-Parser: nur face/alignment
│   │   ├── prompt_planner.py
│   │   ├── prompt_coder.py               ← Layer 2: nur komplexe Stubs
│   │   └── ...
│   ├── rag_db/                           ← ChromaDB Persistenz
│   ├── output/                           ← Generierte STL-Dateien
│   └── sessions/                         ← Lauf-Logs
│       ├── runs.jsonl                    ← Alle Runs (Blueprint, Code, Traces)
│       └── session.json
│
├── src/
│   ├── agents/                           ← Agent-Implementierungen
│   │   ├── base.py
│   │   ├── interpreter.py
│   │   ├── feature_tagger.py
│   │   ├── feature_assigner.py
│   │   ├── feature_position_assigner.py  ← NEU: FPA (nur face/axis_hint)
│   │   ├── part_position_assigner.py     ← NEU: PPA (nur face/alignment)
│   │   ├── blueprint_assembler.py        ← Deterministisch (alle Offsets hier!)
│   │   ├── position_assigner.py          ← Legacy (Dispatcher-Router)
│   │   ├── function_decomposer.py        ← Klassifiziert + generiert Template-Code
│   │   ├── planner.py
│   │   ├── coder.py                      ← Nur Layer 2 (komplexe Stubs)
│   │   └── blueprint_assembler.py
│   ├── codegen/                          ← NEU: Template-Code-Generator (Layer 1)
│   │   ├── __init__.py
│   │   ├── templates.py                  ← Ein Template pro Feature-Typ
│   │   ├── assembler.py                  ← Orchestriert Templates → Python-Script
│   │   └── feature_classifier.py        ← classify_blueprint() → mode
│   ├── config/
│   ├── graph/
│   │   ├── pipeline.py                   ← Inkl. route_after_function_decomposer
│   │   ├── state.py                      ← Inkl. generation_mode Feld
│   │   └── nodes/
│   │       ├── planning_nodes.py
│   │       ├── dispatcher_node.py        ← NEU: Routing FPA vs. PPA
│   │       └── ...
│   ├── rag/
│   │   ├── base_rag.py
│   │   ├── feature_assigner_rag.py
│   │   ├── feature_position_assigner_rag.py  ← NEU (alias: position_assigner_rag)
│   │   ├── part_position_rag.py          ← NEU
│   │   └── ...
│   └── tools/
│
└── config/
    └── config.yaml
```

### Wichtige Pfad-Konventionen
- Prompts: `data/prompts/prompt_*.py`
- CadQuery-RAG: `data/rag/01-16_*/`
- Agent-RAG: `data/knowledge/rag_agents/20-28_*/`
- Template-System: `src/codegen/`
- Agent-Code: `src/agents/*.py`
- Graph-Logik: `src/graph/`
- Alle Runs: `data/sessions/runs.jsonl`

---

## Commit-Nachrichten

Format: `[Bereich] Kurzbeschreibung`

Beispiele:
- `[codegen] Fix slot angle on side faces (>X/<X entlang Y = angle=0)`
- `[assembler] Fix hole_pattern_grid face dims für >X/<X und >Y/<Y`
- `[blueprint-assembler] Directional scoring + offset masking in context extraction`
- `[fpa-prompt] Remove offset calculation, nur face + axis_hint`
- `[ppa-prompt] Remove offset formulas, nur face + alignment`
- `[coder-prompt] Layer 2 Rolle: Template-Code nicht anfassen`
