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

### ⚠ Architektur-Umbau aktiv (seit 2026-05-17)

Die Pipeline wird grundlegend umgebaut — **Master-Plan: ADR 0014**
(`docs/decisions/0014-pipeline-rebuild-clean-architecture.md`). Grund:
wiederkehrende Regressions-Kaskade durch Re-Derivation zwischen Agenten +
Konventions-Fragmentierung. Ziel: ein Textverstaendnis-Schritt pro Aktion
(Klassifizierer), Rest deterministisch, NormalizerAgent eliminiert,
per-Agent-Regression-Suiten als Netz. Bis der Umbau durch ist, sind Teile
der Architektur-Beschreibung unten im Fluss. Pickup-Punkt: Memory
`rebuild_plan_2026_05_17`. CLAUDE.md-Voll-Ueberarbeitung ist Workstream W9.

### Aktueller Stand (2026-05-14)

| Capability | Stand | Coverage |
|---|---|---|
| 1.0 Primitive Assembly | gebaut | Cov 3 (18/18 Component-Goldens grün); fehlt L2-Coverage + Cov 4 STRESS |
| 1.5 Extended Primitives | nicht gebaut | Cov 0 |
| 2.0 Modifications | teilweise (Coder-Pfad) | Cov 0 als Golden |
| 3.0-9.0 | nicht gebaut | Cov 0 |

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
- Aktuell: nemotron-cascade-2:30b (Blueprint Architect), qwen3.5:9b (schnelle Agents)
- Think-Modus: Kritisch fuer raeumliche Aufgaben, ohne Think versagen auch grosse Modelle

## Architektur

### Pipeline Flow (Stand 2026-05-14, Capability 1.0 Cov 3 grün)
```
entry_router → interpreter(9b) → punctuation(26b)
  → inventar(26b, 2-step)               — Teile + Aktions-Liste
  → text_splitter(rule) → position_extractor(26b, per-Teil Labeler)
  → feature_definierer(26b)             — Aktionen → Features
  → platzierer(26b)                     — Multi-Part-Placement
  → assembly(rule) → pocket_child_placer(26b)
  → blueprint_resolver(rule) → coordinate_validator(rule)
  → plan_validator(26b, mit determ. Post-Filter)
  → function_decomposer(rule) → executor(sandbox)
  → geometry_precheck(rule) → validator(26b)
  → [error_router → code_fixer]
```

**Geplante Umstrukturierung (ADR 0003):** Inventar Step B und
feature_definierer werden auf Pro-Aktion-Mikro-Calls aufgeteilt.
Dazwischen kommt ein deterministischer Aktions-Splitter und ein
neuer Aktions-Klassifizierer. Siehe
[`docs/decisions/0003-inventar-feature-definierer-pro-aktion.md`](docs/decisions/0003-inventar-feature-definierer-pro-aktion.md).
Motivation: aktueller Pipeline-Bottleneck ist feature_definierer
(70-313s pro Call) und Inventar verklumpt Tasche+Bohrung-Verschachtelungen
in eine Aktion.

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
src/tools/blueprint_resolver.py — Deterministic: semantic → resolved
src/tools/coordinate_validator.py — Rule-based geometry checks
src/codegen/assembler.py        — Blueprint → CadQuery Code
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
- Die 5 Knotenpunkt-Dateien tragen oben einen STRUKTUR-Kommentarblock:
  pipeline.py, state.py, blueprint_schema.py, assembler.py, templates.py
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

Capability 1.0 Primitive Assembly ist auf Cov 3 (18/18 Component-Goldens
grün, einschliesslich V2_balanced_feature_palette mit DIN-konformer
Slot-Konvention seit 2026-05-14). Naechste Aufgabe: L2-Coverage-Goldens
und L3-STRESS-Goldens schreiben.

L2-Coverage-Goldens (eine Capability komplett pro Test, alle Seiten,
alle Wording-Varianten):
- `B_coverage_all_sides_all_wordings` (Bohrungen)
- `T_coverage_all_sides_all_wordings` (Pockets)
- `N_coverage_all_sides_all_orientations` (Slots)
- `M_coverage_patterns_all_kinds` (Lochmuster Grid/Kreis/Linear)

L3-STRESS-Goldens (Multi-Capability):
- `STRESS_all_in_one_part` (~20+ Features in einem Wuerfel)
- `STRESS_multi_plate_with_features`
- `STRESS_three_plates`
- `STRESS_voice_long`
- `STRESS_anchor_chain`

Wenn alle grün UND Done-Review-Checkliste (ADR 0008) abgehakt:
Capability 1.0 verkaufsreif. Dann Capability 2.0 (Modifications).

### Vorgaengig: Architektur-Refactors die noch laufen

Diese ADRs sind noch nicht vollstaendig umgesetzt und blockieren
Capability-Vorbereitungen:

#### Phase A: 3-Step Chain — UMGESETZT, im Refactor
Der monolithische Blueprint Architect wurde in eine Kette aus
Inventar → feature_definierer → platzierer → assembly aufgeteilt.
Heute produktiv. Schwachstelle: feature_definierer ist trotzdem
ein einziger LLM-Call pro Teil mit allen Aktionen darin — bei
komplexen Specs 70-313s Latenz.

#### Phase A.5: Pro-Aktion-Mikro-Calls (ADR 0003 — UMGESETZT)
Inventar Step B + feature_definierer wurden in Pro-Aktion-Mikro-Calls
zerlegt. Aktions-Splitter + Klassifizierer + per-Phrase Normalizer +
deterministischer Aggregator. Motivation: Bottleneck-Aufloesung,
Bug "Tasche mit Bohrung drin"-Verschachtelung, stabile Aktions-IDs.
Details: ADR 0003.
#### Phase B: Geometry Assertions (deterministisch, geplant)
Aus dem resolved Blueprint automatisch Tests generieren — Volumen, BBox,
Feature-Count. Nach Executor vergleichen: Delta > 5% → Fehler. Ersetzt
langfristig den unzuverlaessigen LLM-Validator. Bezug zur
Capability-Matrix: ist Cov-5/Cov-6 Infrastruktur, parallel zu allen
Capabilities einsetzbar.

#### Phase B Teil 2: Validator-Reverse-Engineering (geplant)
Spiegelbild der Bau-Kette als Validator: viele kleine Experten von HINTEN
nach VORNE, anderes Modell als Bau-Pfad fuer unabhaengige Sicht. Jeder
Validator prueft EIN Aspekt (Position, Drehung, Flaeche, Anker,
Feature-Count). Deterministisch wo moeglich, LLM nur fuer
Textverstaendnis-Pruefung. Bezug: ist Cov-5/Cov-6 Infrastruktur.

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
Sub-Agent (Klassifizierer-Sub-Agents, Normalizer, position_extractor,
platzierer). Reward-Signal aus Geometry Assertions (Volumen/BBox/
Feature-Count Delta). Kleine Datenmengen OK solange Reward-Signal sauber.
Vor Training: Schema eingefroren — sonst Moving Target.

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
- Inventar Step B + feature_definierer: Mega-Calls bei vielen Aktionen
  → Latenz 70-313s, verklumpt Tasche+Bohrung-Verschachtelungen
  → ADR 0003 in Umsetzung: Pro-Aktion-Mikro-Calls
- coordinate_validator bei rotierten Pockets nahe Kante: false positive
  durch konservative bbox-Approximation (max(x,y)/2). Ein eigener
  Fix-Punkt — bisher keine ADR.

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