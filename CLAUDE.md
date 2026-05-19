# 3D AI Pipeline V2

Text-zu-CAD Pipeline: Natuerliche Sprache → Semantisches Blueprint → CadQuery Code → STL

## Projekt-Vision

Text-zu-CAD Pipeline fuer **B2B Maschinenbau-CNC-Konstrukteure**. Eingaben
in Konstrukteur-Sprache nach DIN/ISO-Konvention, Ausgabe als korrekter
CAD-Output (heute STL, perspektivisch STEP/IGES + 2D-Zeichnungs-PDF).
System soll mit kleinen lokalen Modellen (9b-30b) funktionieren. Groessere
Modelle nur als Fallback oder zum Training.

**Verkaufsziel:** professionelles Konstrukteur-Tool, kein Maker-/Hobby-
Tool. Daraus folgt: DIN/ISO-Konformitaet ist Pflicht (nicht Polish),
Toleranzen + Norm-Bauteile + STEP-Export sind Top-Prio.

## Capability×Coverage Matrix (Single Source of Truth fuer Status)

Projekt-Struktur seit ADR 0008. Ersetzt die alte lineare Phasen-Liste.

**Achse 1 — Capabilities** (was die Pipeline kann):

| Stufe | Capability |
|---|---|
| 1.0 | Primitive Assembly (Box/Zylinder + Bohrung/Nut/Tasche/Patterns) |
| 1.5 | Extended Primitives (Polygon 3/4/6/8-eck, Trapez, Kontur-Extrude/Pocket, Auto-Closing-Contours) |
| 2.0 | Modifications (Fasen/Rundungen alle Kanten-Auswahl-Varianten als Templates, Shell) |
| 3.0 | Komplexe Formen (Loft, Sweep, Spline, Revolve) |
| 4.0 | Connections (Senkbohrungen, Gewinde, Durchgangs-Bohrung durch zwei Teile) |
| 5.0 | Assemblies (Bewegliche Teile, kinematische Constraints) |
| 6.0 | Constraint-Bemassung (Origin/Datum, Absolut X/Y/Z, Symmetrie, Feature-Bezug, Auto-fill) |
| 7.0 | Engineering Norms (Toleranzen ISO 286, GD&T ISO 1101, Norm-Bauteile DIN) |
| 8.0 | Professional Output (STEP/IGES, DXF, 2D-Zeichnung-PDF, DFM-Checks) |
| 9.0 | Vision/Drawing Input (Bild oder technische Zeichnung → Blueprint) |

**Achse 2 — Coverage** (Test-Robustheit pro Capability):

| Cov | Definition |
|---|---|
| 0 | Nichts implementiert oder nicht getestet |
| 1 | Component-Goldens grün (Splitter + Resolver isoliert) |
| 2 | Pipeline-Goldens Basics grün (einfacher Real-Run pro Variante) |
| 3 | Coverage-Goldens grün (eine Capability komplett, alle Seiten + Wording-Varianten) |
| 4 | Stress-Goldens grün (Multi-Capability-Kombo, ~20+ Features) |
| 5 | Limit-Tests grün (50+ Features, 8+ Plates) |
| 6 | Real-World Engineering-Validation (extern getestet) |

**Definition of Done pro Capability:** Cov 4 grün + Done-Review-Checkliste
abgehakt (siehe ADR 0008). Cov 5+6 sind Verkaufs-Polish.

### Architektur-Umbau ADR 0014 — fast durch (Stand 2026-05-18)

Die Pipeline wurde nach **ADR 0014**
(`docs/decisions/0014-pipeline-rebuild-clean-architecture.md`)
grundlegend umgebaut. Grund: wiederkehrende Regressions-Kaskade durch
Re-Derivation zwischen Agenten + Konventions-Fragmentierung. Ziel: ein
Textverstaendnis-Schritt pro Aktion, Rest deterministisch.

Workstream-Stand: W1-W7 + W10 **durch** (Agent-Regression-Suiten,
Konventions-Bibliothek, spezifische typ-Klassifizierer, NormalizerAgent-
Elimination, Regex-Audit, KNN-Demos, Mini-Heatmap, Legacy-Architect-
Entfernung). **W8 deferred** — die Schema-v3-Praemisse („chaotische
Merges") war empirisch nicht bestaetigt (0/5316 Features mit
Mehrfach-Positionierung, ADR 0014 §16). **W9** (diese CLAUDE.md-/docs-
Aktualisierung) laeuft. Pickup-Punkt: Memory `rebuild_plan_2026_05_17`.

### Aktueller Stand (2026-05-19)

| Capability | Stand | Coverage |
|---|---|---|
| 1.0 Primitive Assembly | **funktional done** | **Cov 4** (L1 + L2 + 5/5 STRESS-Goldens grün) |
| 1.5 Extended Primitives | nicht gebaut | Cov 0 |
| 2.0 Modifications | teilweise (Coder-Pfad) + Edge-Filter-Quick-Wins als Sub-Items | Cov 0 als Golden |
| 3.0-9.0 | nicht gebaut | Cov 0 |

**Cap 1.0 Done-Review-Stand (ADR 0008):**

- ✅ **Funktional**: L1 Component-Goldens + L2 Coverage-Goldens
  (B/T/N/M_coverage) + L3 STRESS-Goldens (all_in_one_part,
  multi_plate_with_features, three_plates, anchor_chain, voice_long) + DSPy-
  Demos (158 Demos in 7 Pools).
- ✅ **DIN/ISO**: 10/11/20/21/22/24/25/26-Konventions-Docs + 90 Wording-
  Beispiele + Konventions-Walkthrough (4afd59a) gegen ISO 129-1.
- ⚠ **Code-Qualitaet (laufender Refactor-Pass, vorbestehend)**: 59 ruff
  style-Findings + Dateien >500 LOC. Vorbestehend, keine Cap-1.0-Schulden;
  Aufraeumarbeit laeuft als eigener Refactor-Pass parallel zu Cap 2.0.
  **Stand 2026-05-19**: Die drei Monolithen `blueprint_resolver.py`
  (1609 LOC), `assembler.py` (946 LOC) und `coordinate_validator.py`
  (913 LOC) sind je in ein Package zerlegt — kein Kern-Modul mehr
  >500 LOC. Komplexitaets-Findings abgearbeitet: `_compute_offsets`
  F50→D29, `_resolve_feature_in_feature` E31→C15, `_generate_subtract`
  F120→C17, `_check_feature` F44→D24. Code-Qualitaet-Refactor-Pass
  damit abgeschlossen.

### Empfohlene Reihenfolge

1. **1.0 → Cov 4** (STRESS-Goldens schreiben, Capability 1.0 verkaufsreif)
2. **2.0 komplett** (Templates statt Coder-Pfad + Goldens)
3. **6.0 Constraint-Bemassung** (DAS unterscheidet Konstrukteur- von Maker-Tool)
4. **1.5 Extended Primitives + Auto-Close**
5. **4.0 Connections** (Senkungen, Gewinde, Cross-Part)
6. **7.0 Engineering Norms** (Toleranzen)
7. **8.0 Professional Output** (STEP)
8. **3.0 Komplexe Formen**
9. **5.0 Assemblies**
10. **9.0 Vision**

## Hardware & Modelle

- GPU: NVIDIA 5060 Ti 16GB VRAM, 64GB RAM DDR5, AMD 7800X3D
- Max komfortabel: ~35b Modelle, 70b moeglich aber langsam
- Aktuell: gemma4:26b (Klassifizierer/Validator), qwen3.5:9b (schnelle Agents)
- Think-Modus: Kritisch fuer raeumliche Aufgaben, ohne Think versagen auch grosse Modelle

## Architektur

### Pipeline Flow (Stand 2026-05-18, ADR 0003 Per-Aktion-Kette + ADR 0014 W10)
```
entry_router → interpreter → punctuation
  → inventar (Step A: Teile-Liste)
  → aktions_splitter (rule)             — Spec → Aktions-Phrasen
  → aktions_klassifizierer (LLM-Loop)   — 1 typ-Klassifizierer-Call/Phrase
                                          (+ anchor_classifier cue-gated)
  → text_splitter (LLM)                 — per-Teil Chunks fuer Multi-Part
  → position_extractor (LLM)            — placement- vs feature-Labeler
  → feature_definierer (LLM-Loop)       — define_feature pro Klassifikation
  → aktions_aggregator (rule)           — baut teil_definitionen[]
  → platzierer (LLM)                    — Multi-Part-Placement
  → assembly (rule) → pocket_child_placer
  → blueprint_resolver (rule) → coordinate_validator (rule)
  → plan_validator (LLM, mit determ. Post-Filter)
  → function_decomposer (rule) → coder → code_review → executor (sandbox)
  → validator (LLM) → [error_router → code_fixer]
```

EIN Textverstaendnis-Schritt pro Aktion (der typ-Klassifizierer),
Rest deterministisch — Ziel-Architektur aus ADR 0014. Der frueher
monolithische Blueprint-Schritt ist in diese Per-Aktion-Kette zerlegt
(ADR 0003); der NormalizerAgent wurde eliminiert (ADR 0014 W4), der
Legacy-`blueprint_architect`-Fallback entfernt (ADR 0014 W10).
Validation-Failures routen zurueck an den verursachenden Agenten
(coordinate_validator → feature_definierer, plan_validator → assembly).

### Zwei-Schicht Blueprint (V2, seit 2026-04-07)

**Semantisches Blueprint** (KI erzeugt):
- `orientation`: "hochkant", "flach", "standard" — KI rechnet nichts
- `position.side`: "oben", "rechts", "links" — natuerliche Sprache
- `position.alignment`: "centered", "flush_right" — keine Offset-Berechnung
- `position.edge_distances`: {"right": 20} — Abstande in Worten
- `params`: Rohdimensionen wie vom User angegeben

**Resolved Blueprint** (Resolver berechnet deterministisch):
- `placement.face`: ">Z", "<X" etc. — CadQuery Face Selector
- `placement.offset_x/y`: Numerische Offsets
- `params`: Dimensionen nach Orientation-Swap

**Konvention:** "oben" = immer die X*Y Flaeche der Rohdimensionen.
User sagt "100x100x20" → "oben" ist 100x100, auch nach hochkant-Swap.

### Kern-Dateien
```
src/graph/pipeline.py           — LangGraph Verdrahtung
src/graph/state.py              — PipelineState (TypedDict)
src/graph/blueprint_schema.py   — Pydantic Schema (Semantic + Resolved)
src/graph/nodes/                — Alle Pipeline-Nodes
src/tools/blueprint_resolver/   — Deterministic: semantic → resolved (Package)
src/tools/coordinate_validator/  — Rule-based geometry checks (Package)
src/codegen/assembler/          — Blueprint → CadQuery Code (Package)
src/codegen/templates.py        — CadQuery Code-Templates pro Feature
data/prompts/                   — Alle LLM System Prompts
config/config.yaml              — Modelle, Timeouts, RAG Config
data/sessions/runs.jsonl        — Alle Pipeline-Runs mit Traces
```

## Entwicklungs-Prinzipien

### Aufgaben-Trennung: Textverstaendnis = LLM, Rechen = deterministisch
- LLM-Aufgaben: aus Text Bedeutung extrahieren (Containment "in der
  Tasche?", Versatz-Werte, Anker-Vokabular, Aktionen identifizieren).
- Deterministisch: Koordinaten-Mathe, Face-Auswahl, Rotation, Dim-Swap,
  Code-Generierung aus Schema, Assembly via Union/Resolver.
- **Wichtig:** Es gilt NICHT pauschal "Determinismus vor Prompts".
  Determinismus als Pflaster fuer Textverstaendnis-Fehler schafft
  enge Regeln, die zu starke Barrieren fuer den breiten Aufgaben-
  Umfang sind. Wenn ein LLM-Call patzt: zuerst Prompt verbessern oder
  Aufgabe aufteilen.
- Coordinate Validator, Blueprint Resolver, Geometry Precheck =
  zuverlaessig (deterministisch)
- LLM-Validierung = unzuverlaessig (sagt oft "valid" bei offensichtlichen Fehlern)

### Kleine Schritte fuer kleine Modelle
- Komplexe Aufgaben so weit runterbrechen dass ein 9b-Modell sie loesen kann
- Lieber 3 einfache LLM-Calls als 1 komplexer
- Jeder LLM-Call hat EINE klare Aufgabe mit EINEM Ausgabeformat
- Ab gewisser Blueprint-Groesse: splitten und nacheinander verarbeiten

### Schema-Stabilitaet
- Blueprint-Schema (semantic + resolved) ist EINGEFROREN
- Aenderungen nur additiv (neue optionale Felder), nie bestehende Felder umbenennen
- Jeder Run ab jetzt ist valides Trainingsmaterial
- Neue Feature-Typen als Erweiterung, nicht als Schema-Aenderung

### Fehleranalyse
- Runs in data/sessions/runs.jsonl analysieren, immer von HINTEN nach VORNE
- agent_traces zeigen Input/Output jedes Schritts
- Haeufigste Fehlerquellen: LLM-Textverstaendnis > Planner-Logik > CadQuery-Kernel

### STRUKTUR-Header in Kern-Dateien
- Die 5 Knotenpunkte tragen oben einen STRUKTUR-Kommentarblock:
  pipeline.py, state.py, blueprint_schema.py, templates.py und
  assembler/core.py (assembler ist seit 2026-05-19 ein Package — der
  Block sitzt in core.py).
- Der Block listet alle Funktionen/Klassen/Abschnitte mit einem Satz zum Zweck
- Bei jeder Aenderung in einer dieser Dateien: Block pflegen (neue Funktion
  hinzufuegen, entfernte loeschen, umbenannte anpassen). Das ist Teil des Commits.
- Ziel: ohne die ganze Datei zu lesen weiss man was wo liegt
- Keine Zeilennummern im Block — die driften. Nur symbolische Namen.

## Naechste Schritte (Capability-getrieben)

Die naechsten konkreten Schritte ergeben sich aus der Capability-Matrix
oben. Detail-Plan und Reihenfolge in
[`memory/project_next_phase_plan.md`](file:///home/christian/.claude/projects/-home-christian-projects-3D-AI-Pipeline-V2/memory/project_next_phase_plan.md).
Strukturierungs-Entscheidung: ADR 0008.

### Aktueller Fokus: Capability 1.0 → Cov 4

Capability 1.0 Primitive Assembly ist auf Cov 3. Component-Goldens
(Splitter + Resolver isoliert) und L2-Coverage-Goldens sind grün:

L2-Coverage-Goldens (eine Capability komplett pro Test, alle Seiten,
alle Wording-Varianten):
- `B_coverage_all_sides_all_wordings` (Bohrungen)
- `T_coverage_all_sides_all_wordings` (Pockets)
- `N_coverage_all_sides_all_orientations` (Slots)
- `M_coverage_patterns_all_kinds` (Lochmuster Grid/Kreis/Linear)

L3-STRESS-Goldens (Multi-Capability) — Cov-4-Ziel:
- `STRESS_all_in_one_part` (22 Features in einem Wuerfel) — grün (Resolver-Layer)
- `STRESS_multi_plate_with_features` — grün (Resolver-Layer)
- `STRESS_three_plates` — grün (Resolver-Layer)
- `STRESS_anchor_chain` — offen
- `STRESS_voice_long` — offen (Splitter-/Pipeline-Layer)

Die drei gebauten STRESS-Goldens decken den deterministischen
Resolver-Layer ab. Die offenen zwei brauchen den Pipeline-Layer
(Real-Run gegen Ollama). Wenn alle grün UND Done-Review-Checkliste
(ADR 0008) abgehakt: Capability 1.0 verkaufsreif. Dann Capability 2.0
(Modifications).

### Validator-Reverse-Engineering (ADR 0015/0016)

Der LLM-Validator ist unzuverlaessig (sagt oft „valid" bei
offensichtlichen Fehlern). Geplanter Ersatz: ein Reverse-Validator —
Spiegelbild der Bau-Kette, viele kleine Experten von HINTEN nach VORNE,
jeder prueft EINEN Aspekt (Position, Drehung, Flaeche, Anker,
Feature-Count). Deterministisch wo moeglich.

Stand: dormantes Scaffold in `src/validation/` existiert (ADR 0015),
nicht in die Pipeline verdrahtet. Phasenplan fuer den Vollausbau in
ADR 0016 — Trigger: Cap 1.0 Cov 4 + Cap 6.0 (Datums) + Cap 7.0
(Toleranzen). Bis dahin tragen die deterministischen Checks im
`coordinate_validator` die Last.

## Architektur-Notizen fuer spaeter

Diese Sektion haelt Konzepte fest, die zu spaeteren Capabilities
(insbesondere 3.0 Komplexe Formen, 4.0 Connections, 5.0 Assemblies)
gehoeren. Reihenfolge und Details koennen sich aendern.

### Multi-Assembler (Capability 4.0+5.0)
Heute gibt es genau einen Assembler (MergeAssembler via Union).
Geplant sind parallele Assembler, gesteuert ueber `feature.type`:

- **MergeAssembler** (heute): Union-basiertes Verschmelzen zu einem Body.
  Standard fuer Primitiv-Assembly.
- **JoinAssembler** (neu): Teile bleiben getrennte Bodies und werden ueber
  definierte Anschlussflaechen verbunden. Braucht CadQuery `Assembly`-API.
  Use-Case: Scharniere, Verschraubungen, bewegliche Teile.
- **ContourAssembler** (neu): 2D-Pfad (Segmentliste) → Extrude. Fuer
  Freiform-Platten, die als "von links nach rechts 100, dann Bogen R20,
  dann nach oben 50" beschrieben werden.
- **RevolveAssembler** (neu): Profil + Achse → Revolve mit optionalem
  Teilwinkel (Default 360 Grad). Fuer runde Teile mit Kontur-Definition.

Jeder Assembler liest denselben resolved Blueprint, liefert CadQuery-Code
fuer seinen Typ-Bereich. Der function_decomposer routet nach `type` an den
richtigen Assembler.

### ContourSpecifier-Agent (Capability 1.5/3.0)
Neuer 9b-Agent, der nur eine Aufgabe hat: Freitext-Kontur → strukturierte
Segmentliste (path).

- Triggert nur, wenn Interpreter `part_shape_mode = contour|revolve` setzt
- Pro Kontur-Teil ein Call (kleine Schritte fuer kleine Modelle)
- Output wird durch deterministischen ContourValidator geprueft:
  geschlossener Pfad? Arc-Segmente vollstaendig? Keine Selbstschnitte?
- Neue Schema-Felder (additiv): `params.path` als Segmentliste,
  `params.axis` fuer Revolve, `params.angle_deg` fuer Teilrotation

Beispiel-Segmente: `{move: "right", length: 100}`, `{arc: {radius, dir, end_offset}}`,
`{turn: -40}`, `{close: true}`.

### Spezialisten-Agents (bei Bedarf aufteilen, Capability 1.5/3.0 (additiv splittbar))
Wenn der ContourSpecifier zu viele Sub-Faelle abdecken muss, weiter splitten:
Arc-Specifier, Sweep-Specifier, Revolve-Specifier. Jeder ein eigener 9b-Call.
Erst aufteilen, wenn ein einzelner Agent empirisch ueberfordert ist — nicht
vorsorglich.

### UI-Assembler-Tab (Face-Picking, vor Capability 1.5)
Zweiter UI-Tab (ersetzt oder ergaenzt den heutigen "Result"-Bereich):

- 3D-Viewer zeigt aktuelles Teil, Flaechen anklickbar
- Ausgewaehlte Flaeche wird dem Agent als strukturierter Hinweis uebergeben
  (Face-ID, BBox, Normale) → kein Raten aus Text
- Aktionen auf Flaeche: Bohrung setzen, Toleranz aendern, Nut, Tasche
- Zweites Teil aus Historie/Ordner laden → beide Teile sichtbar →
  Flaechen auf beiden Teilen waehlen → "verbinde diese Flaechen"
  triggert JoinAssembler
- Nuetzlich auch fuer simple Faelle (praezise Bohrung setzen), nicht nur
  fuer Konturen. Deshalb vor den Konturen einbauen.

### Modify-vs-neu Decider (Capability 4.0+5.0)
Heute muss der User die Datei abschliessen, bevor ein neues Teil
generiert wird. Deterministische Loesung:

- Leere Session oder expliziter "neu/reset"-Trigger → neu
- Aktives Teil + Keywords ("aendere", "fuege hinzu", "entferne", "an",
  "zusaetzlich") → modify
- Ein schmaler Pre-Schritt im entry_router, rein regelbasiert
- LLM-Fallback nur, wenn empirisch zu oft falsch entschieden

### Projekt-/Ordner-Agent (Capability 8.0+)
Autonome Struktur fuer mehrere Projekte:

- Thin LLM-Classifier: "neues Projekt?" vs. "in Projekt X ablegen?"
- Ordner-Erzeugung und Teile-Zuordnung
- Historie pro Projekt
- NICHT vor Capability 4.0+ bauen — organisatorisches Feature, kein
  Fortschritt am Kernproblem.

### Modification-Kontext (Capability 4.0+5.0)
Problem: Bei Modifikationen muessen die Agents wissen was schon da ist
(welche Teile, wo liegen sie, welche Features hat welches Teil). Ohne
diesen Kontext weiss der Teil-Definierer nicht ob er ein neues Teil
beschreibt oder ein bestehendes erweitert.

Geplanter Ansatz: Gleiche Agent-Kette wie beim Frisch-Run, aber mit
einem **Modification-Digest** als zusaetzlichem Input:

- Deterministischer Pre-Schritt nimmt das `previous_blueprint` und
  erzeugt einen kurzen Klartext-Report:
  "Vorhanden: Teil A (Wuerfel 50x50x50) mit Bohrung zentral R10.
   Teil B (Platte 40x40x20) rechts an Teil A, hochkant."
- Dieser Digest wird zusammen mit dem Modification-Text an Inventar,
  Teil-Definierer und Assembly uebergeben
- Der Modify-vs-neu Decider entscheidet ob das neue Blueprint das alte
  ERWEITERT (neue Teile/Features hinzu) oder EIN TEIL VERAENDERT
  (bestehendes Teil mit neuer Param-/Feature-Liste ueberschreibt)
- Schema-Aenderung: keine. Nur der Prompt-Assembler liest `previous_blueprint`
  und fuegt den Digest ein

Offen: Ob das zerpflueckte Blueprint als strukturierter Zusatz (JSON)
oder als Klartext-Digest besser funktioniert — empirisch testen sobald
Frisch-Runs stabil laufen. Jetzt nicht implementieren.

### Training-Pairing (Good/Bad-Runs, parallel zu Cov-3+ Goldens)
Problem: Wenn ein Run fehlschlaegt (z.B. falscher Agent zugewiesen) und
der naechste Versuch erfolgreich ist, sind beide Runs als Trainingsdaten
interessant — aber nur, wenn sie als Paar erkennbar sind.

Geplanter Mechanismus:

- UI-Button "Als Paar fuer Training markieren" nach einem erfolgreichen
  Run, der einen vorherigen fehlerhaften Run zum gleichen raw_input
  automatisch vorschlaegt
- Automatischer Paarungs-Kandidat: gleicher oder sehr aehnlicher
  raw_input innerhalb eines Zeitfensters, bei dem ein frueherer Run
  Error/Validator-Feedback hat und der spaetere success=True
- Paar wird in `data/sessions/training_pairs.jsonl` persistiert mit:
  {bad_run_id, good_run_id, raw_input, failure_reason, success_delta}
- Vorteil fuer DSPy: explizite Negativbeispiele, nicht nur Positivdaten
- Manueller Override moeglich: User kann auch Runs mit unterschiedlichem
  Wortlaut paaren (gleiches Ziel, andere Formulierung)

Jetzt nicht implementieren. Sobald Capability 1.0 Cov 4 grün ist und DSPy-Training
startet, wird das zur relevanten Datenquelle.

### DSPy-Training-Strategie
Sobald Capability 1.0 Cov 4 grün ist: einmaliges Baseline-Training pro
Sub-Agent (Klassifizierer-Sub-Agents, position_extractor, platzierer,
inventar). Reward-Signal aus Geometry Assertions (Volumen/BBox/
Feature-Count Delta). Kleine Datenmengen OK solange Reward-Signal sauber.
Vor Training: Schema eingefroren — sonst Moving Target. Die Klassifizierer
nutzen seit ADR 0014 W6 KNN-Demo-Retrieval — Pool-Pflege
(`klassifizierer_traces.py` + `make demo-pools`) ist laufende Aufgabe.

## Bekannte Limitierungen

- CadQuery/OCCT: Non-manifold Tessellation bei flush-edge Unions
  → Workaround: 0.01mm Inset oder .clean() nach jeder Union
- Kleine Modelle (9b): Versagen bei raeumlichem Reasoning ohne Think-Modus
- Validator (LLM): Sagt oft "valid" bei offensichtlichen Fehlern
  → Wird durch deterministische Geometry Assertions ersetzt (Cov-5+6 Infrastruktur)
  → Konkrete bekannte False-Positives haben deterministische Post-Filter
    (z.B. plan_validator pocket_floor — siehe ADR 0002)
- Fix-Loop: KI gibt manchmal resolved statt semantic Format zurueck
  → Resolver handhabt das jetzt (orientation wird trotzdem angewandt)
- ~~Inventar Step B + feature_definierer: Mega-Calls bei vielen Aktionen
  (Latenz 70-313s, verklumpt Tasche+Bohrung-Verschachtelungen).~~
  Behoben: ADR 0003 Per-Aktion-Mikro-Calls umgesetzt — Inventar macht
  nur noch Step A (Teile-Liste), die Aktions-Verarbeitung laeuft als
  aktions_splitter → aktions_klassifizierer → feature_definierer-Loop.
- ~~coordinate_validator bei rotierten Pockets nahe Kante: bbox-
  Approximation ignoriert Rotation.~~ Behoben 2026-05-18: `_check_offset_bounds`
  rechnet jetzt rotations-bewusst (x_half·cos|θ| + y_half·sin|θ|) — fasst
  die echte AABB der rotierten Tasche und meldet vorher uebersehene
  Ueberhaenge. Unit-Tests in `tests/tools/test_coordinate_validator.py`.

## Dokumentations-Konventionen

- **CLAUDE.md** (diese Datei): Vision, Architektur-Ueberblick, aktive
  Roadmap-Items, Kern-Dateien-Map. Bleibt das Einsteiger-Dokument.
- **CHANGELOG.md**: chronologischer Eintrag pro nennenswerter Aenderung
  mit Commit-Hash. Kein Versionsschema, nur Datum.
- **docs/decisions/**: Architecture Decision Records (ADRs). Pro
  groesserer Architektur-Entscheidung eine Datei mit Kontext, Entscheidung,
  verworfenen Alternativen, Konsequenzen. Pflichtbestandteil bei Refactor.
- **memory/**: persistenter Claude-Kontext, von claude-code automatisch
  gepflegt. Nicht im Repo.