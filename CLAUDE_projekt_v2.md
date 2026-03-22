# CLAUDE.md — 3D AI Pipeline V2

## Projekt-Überblick

LangGraph-basierte Multi-Agent-Pipeline die natürlichsprachliche Beschreibungen
(deutsch) in CadQuery-3D-Modelle (STL) umwandelt. Langfristiges Ziel: kommerzielles
B2B-Produkt für die Fertigungsindustrie.

**Architektur:** Interpreter → Feature Tagger → Planner → Validators → 
Function Decomposer → Coder → Code Review → Executor → Geometry Checker → Validator

**Modelle (aktuell):**
- qwen3.5:9b — Feature Tagger, Plan Validator, Code Review
- qwen3.5:35b — Interpreter, Planner
- qwen3-coder:30b — Coder

**Stack:** Python 3.12, LangGraph, CadQuery, Ollama, ChromaDB (RAG), Pop!_OS Linux

---

## Kern-Prinzipien

### 1. Produktionsqualität
- Jede Änderung muss so geschrieben sein als ginge sie in Produktion
- Type Hints überall, Docstrings bei jeder öffentlichen Funktion
- Error Handling mit spezifischen Exceptions, nie bare `except:`
- Keine `from module import *` (= Wildcard-Imports) — immer explizit importieren

### 2. Stabilität vor Features
- Bestehende funktionierende Features NIEMALS durch Änderungen brechen
- Bei jeder Änderung: "Kann das einen bestehenden Testfall kaputt machen?"
- Rückwärtskompatibilität bei Schema-Änderungen (Blueprint JSON etc.)
- Änderungen inkrementell — lieber 3 kleine Schritte als 1 riesiger Umbau

### 3. Messbare Verbesserungen
- Jede Optimierung muss durch echte Pipeline-Runs verifiziert werden
- Testfälle in die Pipeline schicken, Logs prüfen (nicht nur Unit Tests)
- Die echten Probleme zeigen sich erst im End-to-End-Lauf mit LLM-Antworten
- "Gefühlt besser" reicht nicht — Erfolgsrate, Retries und STL-Korrektheit zählen

### 4. Agent-Isolation
- Jeder Agent hat seine eigene Welt: eigenes RAG, eigenen Prompt, eigenes Schema
- NIEMALS CadQuery-Code in Planner-Prompts, NIEMALS Geometrie-Theorie in Coder-Prompts
- Wenn ein Agent schlecht arbeitet: nur SEINEN Prompt/RAG ändern
- Seiteneffekte zwischen Agents aktiv vermeiden

---

## Code-Standards

### Python-Stil
```python
# RICHTIG:
def validate_blueprint(blueprint: dict, spec: str) -> ValidationResult:
    """Prüft den Blueprint gegen die Spezifikation.
    
    Args:
        blueprint: Feature Tree JSON vom Planner
        spec: Originale Interpreter-Spezifikation
        
    Returns:
        ValidationResult mit is_valid und issues
        
    Raises:
        BlueprintSchemaError: Wenn blueprint ungültiges Format hat
    """

# FALSCH:
def validate(bp, s):
    # prüft blueprint
```

### Funktionslänge
- Einzelne Funktionen: max ~50 Zeilen (darüber → in Teilfunktionen aufteilen)
- Gilt für Funktionen, NICHT für Dateien — Prompt-Dateien, Configs etc. dürfen länger sein
- Wenn eine Funktion zu lang wird: Logik in Helper-Funktionen auslagern

### Imports
- Standardlib → Third-Party → Lokale Module (in dieser Reihenfolge)
- Immer explizite Imports: `from os import path, listdir`
- NIEMALS: `from os import *` (Wildcard-Imports — unklar was importiert wird)
- Keine ungenutzten Imports

### Konfiguration
- Alle Agent-Configs zentral in `data/prompts/agent_config.py`
- App-Level Config in `src/config/` und `config/`
- Keine hartkodierten Modellnamen, Temperaturen, Token-Limits im Agent-Code
- Pfade über Config, nie hardcoded

### Logging
- Jeder Agent-Call: Start (mit Input-Zusammenfassung), Ende (mit Output-Zusammenfassung)
- Jeder Fehler: vollständiger Kontext (welcher Agent, welcher Input, welcher Fehler)
- Strukturiertes Logging (JSON) für spätere Analyse

---

## Architektur-Regeln

### LangGraph-Nodes
- Agent-Implementierungen in `src/agents/` (erben von `base.py`)
- Graph-Definition in `src/graph/`
- Node-Funktion nimmt State, gibt State zurück
- Keine Seiteneffekte außer Logging
- Jeder Node hat einen klar definierten Input/Output-Vertrag (TypedDict)

### RAG-System
- RAG-Verzeichnisse strikt nach Agent getrennt:
  - `data/rag/01-15_*` → NUR für Coder
  - `data/rag_agents/20_*` → NUR für Feature Tagger
  - `data/rag_agents/21_*` → NUR für Planner
  - `data/rag_agents/22_*` → NUR für Plan Validator
  - `data/rag_agents/23_*` → NUR für Code Review
  - `data/rag/16_*` → NUR für Interpreter
- Planner hat ZUSÄTZLICH eigene Regel-Dateien in `data/knowledge/planner/rules/`
- RAG-Loader/Query-Logik in `src/rag/`
- ChromaDB-Persistenz in `data/rag_db/`
- Jedes RAG-Dokument folgt dem einheitlichen Format (Tags, Wann verwenden, Code, Fehler)
- Neue RAG-Dokumente müssen getesteten, lauffähigen Code enthalten

### Prompts
- Prompt-Templates in `data/prompts/prompt_*.py`
- Planner hat Template-Dateien nach Aufgabentyp in `data/prompts/planner/template_*.md`
- Agent-Konfiguration zentral in `data/prompts/agent_config.py`
- Prompts NIEMALS inline im Agent-Code — immer aus Prompt-Datei laden

### Kontextqualität nach Modellgröße
Die Modelle haben große Kontextfenster (~128-250k Tokens), aber die QUALITÄT
der Antworten sinkt wenn der Prompt zu voll ist. Das ist kein Kostenproblem
sondern ein Aufmerksamkeits-Problem:

**9b Modelle (Feature Tagger, Plan Validator, Code Review):**
- Max ~13 Regeln im System-Prompt — darüber werden Regeln ignoriert
- RAG-Kontext kurz halten (2-3 kompakte Chunks)
- Klare Enum-Listen statt Freitext
- JSON-Schema für Output-Format immer mitgeben
- 1 konkretes Beispiel (Input → Output) reicht

**35b Modelle (Interpreter, Planner):**
- Deutlich mehr Regeln verkraftbar (~20-25)
- Können längere RAG-Kontexte sinnvoll verarbeiten (4-6 Chunks)
- Chain-of-Thought funktioniert ("Denke Schritt für Schritt")
- 2-3 Beispiele (positiv + negativ) möglich
- Komplexeres Reasoning OK

**30b Coder-Modell:**
- Code-spezialisiert — versteht CadQuery-Patterns gut
- Braucht konkrete Code-Beispiele im RAG (nicht nur Regeln)
- Kann längere RAG-Kontexte verarbeiten
- Skeleton vom Decomposer hilft massiv als Struktur-Vorgabe

### Keine parallelen Modelle
Parallele LLM-Calls auf derselben Maschine verdoppeln die Response-Zeit
statt sie zu halbieren (GPU-Contention). Agents sequenziell ausführen.

### Blueprint JSON Schema
- Änderungen am Schema rückwärtskompatibel (neue Felder optional mit Default)
- Schema-Version tracken

---

## Proaktive Verbesserungen

Wenn dir bei der Arbeit etwas auffällt, weise AKTIV darauf hin:

### Immer melden:
- Duplizierter Code (→ in shared Utility auslagern?)
- Inkonsistente Benennungen (→ vereinheitlichen)
- Fehlende Error-Handling-Pfade
- RAG-Dokumente die veraltet oder widersprüchlich sind
- Prompt-Formulierungen die für das jeweilige Modell zu komplex sind
- Möglichkeiten für regelbasierte Checks statt LLM-Calls (oft zuverlässiger!)
- Architektur-Stellen wo ein größerer Umbau langfristig sinnvoller wäre als Patches
- Potenzial für bessere Struktur oder Erweiterbarkeit

### Format für Vorschläge:
```
⚡ VERBESSERUNGSVORSCHLAG:
Was: [kurze Beschreibung]
Warum: [erwarteter Nutzen — Stabilität/Performance/Fehlerrate]
Aufwand: [gering/mittel/hoch]
Priorität: [sofort/bald/irgendwann]
```

---

## Änderungs-Checkliste

Vor JEDER Änderung an der Pipeline:

### Prompt-Änderungen
- [ ] Regelanzahl im Rahmen? (9b ≤ 13, 35b ≤ 25)
- [ ] Nur den betroffenen Agent-Prompt geändert?
- [ ] Keine Seiteneffekte auf andere Agents?
- [ ] Durch echte Pipeline-Runs verifiziert (nicht nur Unit Tests)?

### RAG-Änderungen
- [ ] Code im RAG-Dokument ist lauffähig und getestet?
- [ ] Tags korrekt für Retrieval?
- [ ] Kein CadQuery-Code in Agent-RAGs (20-23)?

### Code-Änderungen
- [ ] Type Hints vollständig?
- [ ] Docstring bei öffentlichen Funktionen?
- [ ] Error Handling spezifisch?
- [ ] Bestehende Pipeline-Runs brechen nicht?

### Schema-Änderungen (Blueprint, State, etc.)
- [ ] Rückwärtskompatibel? (neue Felder optional mit Default)
- [ ] Alle Nodes die das Schema lesen aktualisiert?

---

## Test-Strategie

### Echte Pipeline-Runs sind der einzige valide Test
Unit Tests fangen Code-Bugs, aber die ECHTEN Probleme kommen von den
LLM-Antworten. Diese zeigen sich nur im End-to-End-Lauf. Deshalb:

### Standard-Testfälle (nach jeder relevanten Änderung durchschicken)
1. **Einfach:** "30mm Würfel"
2. **Subtraktiv:** "30mm Würfel mit 5x5 Nut oben entlang Y und ∅10mm Bohrung 29mm tief"
3. **Additiv:** "100x100x20 Platte mit 20x50x40 Aufsatz rechts oben"
4. **Komplex:** "100x100x20 Platte mit Lochkreis ∅60 mit 6 Löchern ∅6 und Steg 10x80x20 rechts"

### Was bei jedem Run im Log prüfen:
- success=true?
- Retries ≤ 2?
- Volume plausibel?
- BBox plausibel? (Z-Höhe = Basis + Feature!)
- watertight=true?
- Kein sinnloser Loop (gleicher Code 3x generiert)?

---

## Langfristige Architektur

### Wann lohnt sich ein größerer Umbau?
- Wenn die gleiche Fehlerklasse in > 30% der Runs auftritt
- Wenn ein Workaround mehr Code erzeugt als die richtige Lösung
- Wenn eine Komponente > 3 Hotfixes in einer Woche braucht

### Modell-Alternativen evaluieren wenn:
- Ein 9b-Agent konstant halluziniert → auf regelbasiert umstellen (KEIN LLM)
- Der Planner geometrisch falsch rechnet → Planner-RAG erweitern
- Gesamtlaufzeit zu hoch → prüfen welche Agents regelbasiert werden können

### Aktuell empfohlene Modell-Konfiguration:
| Agent | Aktuell | Alternative wenn Probleme |
|-------|---------|--------------------------|
| Interpreter | qwen3.5:35b | (schon upgradet) |
| Feature Tagger | qwen3.5:9b | Regelbasiert (kein LLM) |
| Planner | qwen3.5:35b | (bleibt, RAG verbessern) |
| Plan Validator | qwen3.5:9b | Regelbasiert (kein LLM) |
| Coder | qwen3-coder:30b | (bleibt, RAG verbessern) |
| Code Review | qwen3.5:9b | Regelbasiert + AST-Check |
| Validator | qwen3.5:9b | Regelbasiert (kein LLM) |

**Empfehlung:** Feature Tagger, Plan Validator, Code Review und Validator
sind Kandidaten für regelbasierte Umstellung — deterministische Python-Logik
ist oft zuverlässiger als ein 9b-LLM für Checklisten-Aufgaben.

---

## Dateistruktur

```
3D_AI_Pipeline_V2/
├── CLAUDE.md                          ← DU BIST HIER
│
├── data/
│   ├── knowledge/
│   │   └── planner/rules/             ← Planner-Regeln (nicht RAG, direkt injiziert)
│   │       ├── rules_boolean_order.md
│   │       ├── rules_fillets.md
│   │       ├── rules_grooves.md
│   │       ├── rules_holes.md
│   │       ├── rules_patterns.md
│   │       └── rules_workplane.md
│   ├── rag/                           ← CadQuery-RAG für Coder + Interpreter
│   │   ├── 01_foundations/
│   │   ├── 02_primitives/
│   │   ├── 04_extrusion_operations/
│   │   ├── 05_holes/
│   │   ├── 06_modifiers/
│   │   ├── 07_selectors/
│   │   ├── 08_boolean_operations/
│   │   ├── 13_composition/
│   │   ├── 14_code_patterns/
│   │   └── 16_interpreter_knowledge/
│   ├── rag_agents/                    ← Agent-spezifische RAGs
│   │   ├── 20_feature_catalog/
│   │   ├── 21_planner_geometry/
│   │   ├── 22_plan_validation/
│   │   └── 23_code_review/
│   ├── prompts/                       ← Prompt-Templates + Agent-Config
│   │   ├── planner/                   ← Planner-Templates nach Aufgabentyp
│   │   │   ├── template_boolean.md
│   │   │   ├── template_complex.md
│   │   │   ├── template_feature_add.md
│   │   │   ├── template_feature_subtract.md
│   │   │   ├── template_modify.md
│   │   │   ├── template_pattern.md
│   │   │   └── template_simple.md
│   │   ├── agent_config.py
│   │   ├── function_decomposer.py
│   │   ├── prompt_code_fixer.py
│   │   ├── prompt_code_review.py
│   │   ├── prompt_coder.py
│   │   ├── prompt_feature_tagger.py
│   │   ├── prompt_interpreter.py
│   │   ├── prompt_modification_interpreter.py
│   │   ├── prompt_plan_validator.py
│   │   ├── prompt_planner.py
│   │   ├── prompt_validator.py
│   │   └── prompt_visioner.py
│   ├── rag_db/                        ← ChromaDB Persistenz
│   ├── output/                        ← Generierte STL-Dateien
│   └── sessions/                      ← Lauf-Logs
│       ├── runs.jsonl
│       └── session.json
│
├── src/
│   ├── agents/                        ← Agent-Implementierungen
│   │   ├── base.py                    ← Basis-Agent-Klasse
│   │   ├── code_fixer.py
│   │   ├── code_review.py
│   │   ├── coder.py
│   │   ├── feature_tagger.py
│   │   ├── function_decomposer.py
│   │   ├── interpreter.py
│   │   ├── modification_interpreter.py
│   │   ├── plan_validator.py
│   │   ├── planner.py
│   │   ├── printer.py
│   │   ├── prompt_assembler.py
│   │   ├── validator.py
│   │   └── visioner.py
│   ├── config/                        ← App-Konfiguration
│   ├── graph/                         ← LangGraph-Definition
│   ├── rag/                           ← RAG-Loader/Query-Logik
│   └── tools/                         ← Hilfsfunktionen (Sandbox, STL-Check etc.)
│
└── config/                            ← Projekt-Level-Config
```

### Wichtige Pfad-Konventionen
- Prompts: `data/prompts/prompt_*.py`
- Planner-Templates: `data/prompts/planner/template_*.md`
- Planner-Regeln: `data/knowledge/planner/rules/rules_*.md`
- CadQuery-RAG: `data/rag/01-16_*/`
- Agent-RAG: `data/rag_agents/20-23_*/`
- Agent-Code: `src/agents/*.py`
- Graph-Logik: `src/graph/`

---

## Commit-Nachrichten

Format: `[Agent/Bereich] Kurzbeschreibung`

Beispiele:
- `[coder-prompt] Fix translate_z Berechnung für centered-Flag`
- `[code-review] Entferne Check 19 (verursacht false positives)`
- `[planner-rag] Ergänze bolt_circle_geometry mit Radius/Durchmesser-Warnung`
- `[decomposer] Berechne flush_right Offset regelbasiert`
- `[executor] STL-Export Toleranz-Fallback bei watertight-Fehlern`
