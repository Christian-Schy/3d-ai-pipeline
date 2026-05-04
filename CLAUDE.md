# 3D AI Pipeline V2

Text-zu-CAD Pipeline: Natuerliche Sprache → Semantisches Blueprint → CadQuery Code → STL

## Projekt-Vision

Komplexe 3D-Bauteile aus Textbeschreibungen generieren. Langfristig auch aus
Bildern/Skizzen. System soll mit kleinen lokalen Modellen (9b-30b) funktionieren.
Groessere Modelle nur als Fallback oder zum Training.

**Stufenplan:**
```
Stufe 1: Primitive Assembly        ← AKTUELL
         Boxen, Zylinder, Kugeln, Bohrungen, Nuten, Taschen
         Mehrere Teile korrekt zusammenfuegen (2-5 Teile)

Stufe 2: Verbindungen
         Verschraubungen (Bohrung + Gewinde auf beiden Seiten)
         Scharniere, Clips, Snap-Fits
         "connection"-Feature das automatisch beide Seiten bohrt

Stufe 3: Komplexe Formen
         Loft, Sweep, Spline, Revolution
         Halbkugel subtrahieren, Konus, Bogenausschnitte
         Aerodynamische/geschwungene Konturen

Stufe 4: Organisch/Parametrisch
         Bild → Masse schaetzen → Blueprint generieren
         Mehrteilige bewegliche Teile (Armsleeve, Gelenke)
         Verschlussmechanismen als eigene Feature-Bibliothek
```

## Hardware & Modelle

- GPU: NVIDIA 5060 Ti 16GB VRAM, 64GB RAM DDR5, AMD 7800X3D
- Max komfortabel: ~35b Modelle, 70b moeglich aber langsam
- Aktuell: nemotron-cascade-2:30b (Blueprint Architect), qwen3.5:9b (schnelle Agents)
- Think-Modus: Kritisch fuer raeumliche Aufgaben, ohne Think versagen auch grosse Modelle

## Architektur

### Pipeline Flow
```
entry_router → interpreter(9b) → blueprint_architect(30b)
  → blueprint_resolver(rule) → coordinate_validator(rule)
  → plan_validator(9b) → function_decomposer(rule)
  → [coder(30b) → code_review] → executor(sandbox)
  → geometry_precheck(rule) → validator(9b)
  → [error_router → code_fixer]
```

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

### Determinismus vor Prompts
- Jedes Problem das deterministisch loesbar ist, NICHT per Prompt loesen
- LLM nur fuer Textverstaendnis und semantische Interpretation
- Mathe, Offsets, Face-Berechnung, Dimension-Swaps → immer Code
- Coordinate Validator, Blueprint Resolver, Geometry Precheck = zuverlaessig
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

## Naechste Schritte (Roadmap)

### Phase A: Blueprint Architect → 3-Step Chain (NAECHSTES)
Den monolithischen Blueprint Architect in 3 einfache Schritte aufteilen:

**Step 1 — Inventar (9b, schnell):**
Input: User-Text
Output: Stueckliste mit Teile-Count, Teile-Namen, Rohdimensionen
"Wie viele Teile? Liste sie auf mit Massen."

**Step 2 — Teil-Definition (9b, pro Teil wiederholbar):**
Input: Ein einzelnes Teil aus der Stueckliste + relevanter Kontext
Output: Semantisches Feature fuer dieses Teil (type, params, orientation)
"Beschreibe dieses eine Teil mit seinen Aktionen."

**Step 3 — Assembly (9b, einmalig):**
Input: Alle Teil-Definitionen + User-Text
Output: Vollstaendiges semantisches Blueprint (parent/position Beziehungen)
"Wie haengen die Teile zusammen?"

Vorteile:
- Jeder Schritt ist trivial genug fuer kleine Modelle
- Teil-Count vorab bekannt → KI erfindet keine Extra-Teile
- Pro-Teil Definition skaliert: 3 Teile = 3 Calls, 20 Teile = 20 Calls
- Bei langen Blueprints: Batching moeglich
- Fehler isolierbar: welcher Schritt hat versagt?

### Phase B: Geometry Assertions (deterministisch)
Aus dem resolved Blueprint automatisch Tests generieren:
- Erwartetes Volumen berechnen (Summe aller Teile minus Subtraktionen)
- Erwartete BBox berechnen
- Feature-Count verifizieren (Anzahl Bohrungen, Teile)
- Nach Executor vergleichen: Delta > 5% → Fehler
- Ersetzt langfristig den unzuverlaessigen LLM-Validator

### Phase C: Verbindungs-Features
- Neuer semantischer Typ "connection" (Verschraubung, Scharnier, etc.)
- Resolver erzeugt automatisch Bohrungen auf beiden Seiten
- Unterstuetzung fuer Winkel-Verbindungen
- Gewinde als Feature-Typ

### Phase D: Komplexe Formen
- Templates fuer Loft, Sweep, Revolution, Spline
- LLM-Codegen fuer nicht-template-faehige Formen
- RAG mit Beispiel-Code fuer komplexe CadQuery-Operationen

### Phase E: Vision → Blueprint
- Bild/Skizze → VisionerAgent schaetzt Masse
- Partielle Specification → Interpreter vervollstaendigt
- Training auf gesammelten Blueprint-Daten

## Phase-1-Abschluss (Scope-Grenze fuer die aktuelle Baseline)

Phase 1 wird versiegelt wenn folgende Punkte stabil laufen:

1. ✓ 3-Step Blueprint Chain (Inventar → Teil-Definition → Assembly) produktiv
2. ✓ Anchoring-Vokabular: jede Ecke/Kante/Flaeche eines Teils kann auf jede
   Ecke/Kante/Flaeche des Eltern-Teils gesetzt werden, inklusive Rotation
   VOR dem Anchoring. Beispiel: "obere linke Ecke von Platte B liegt auf
   linker Kante von Wuerfel A, 10mm versetzt, 10 Grad CCW gedreht"
   Code-Pfad: SemanticAnchor → blueprint_resolver._apply_anchor →
   assembler._emit_pre_rotation + _emit_face_rotation. Tests in
   tests/tools/test_anchor_placement.py + test_position_builder_anchor.py
   + test_assembler_rotation.py (45 tests gruen).
3. ✓ Feature-Positions-Vokabular erweitert: "in der Ecke", "entlang Kante",
   "diagonal", "versatz innen/aussen", "parallel zu Achse", "symmetrisch".
   Empirisch erreicht 2026-05-04 mit Run 3755d81b (3-Teile-Spec mit anchor +
   edge-distance + nach-aussen, vorher Failcase 91e9771c). 21 Trainings-
   Cases in data/dspy_training/labeler_platzierer_traces.py, position_extractor
   reshaped als per-Teil Labeler, _parse_kv akkumuliert Multi-Line-Keys.
   Siehe Memory project_session_2026_05_04_labeler.md.
4. Nuten in jeder Variation platzierbar: ueber Flaeche, an Kante, parallel
   zu Achse, mit Anker-Vokabular. Pockets + Bohrungen + Quader-Extrusionen
   funktionieren bereits — Nuten nutzen dasselbe Vokabular und sollten
   durch dieselbe Trainings-Strategie greifen. Vor 4 noch sichern: Punkt 3
   stabil ueber mehrere reale Runs (auch Pocket-Cases P1-P4 die noch nie
   real getestet wurden).
5. Fasen + Rundungen sauber ausbauen: alle Kanten-Auswahl-Varianten (eine
   Kante, alle horizontalen, alle vertikalen, eine Flaeche umlaufend),
   sowohl als Fase als auch als Rundung mit Radius/Schraegenmass. Heute
   teilweise im Coder-Pfad — soll auf Templates wie der Rest umziehen.
6. Validator-Kette als Reverse-Engineering (Phase B Teil 2):
   - Spiegelbild der Bau-Kette: viele kleine Experten + deterministische
     Schritte, aber von HINTEN nach VORNE
   - Anderes Modell als der Bau-Pfad fuer unabhaengige Sicht
   - Jeder Validator-Agent bekommt User-Text + Spec + Bau-Output und
     prueft EIN Aspekt (Position, Drehung, Flaeche, Anker, Feature-Count)
   - Deterministisch wo moeglich (Geometry Assertions: Volumen, BBox,
     Feature-Count), LLM nur fuer Textverstaendnis-Pruefung
   - Kontrolle muss schneller als Erstellung gehen
   - Modular, wartbar, sauber — gleiche Prinzipien wie der Bau-Pfad
7. DSPy-Training auf der stabilen Baseline (Prompts von Inventar,
   Teil-Definierer, Assembly, PositionExtractor separat trainiert)

★ NAECHSTER SCHRITT: Punkt 3 in mehr realen Runs verifizieren (Pocket-Cases
  P1-P4 noch ungetestet). Danach Punkt 4 (Nuten) bauen, dann Punkt 5
  (Fasen/Rundungen ausbauen), dann Punkt 6 (Validator-Reverse-Kette).
  Erst nach Punkt 6 Punkt 7 (DSPy-Re-Train auf konsolidierter Baseline).

Nach Phase 1: alle weiteren Phasen (B Teil 2, C, D, E, F) bauen additiv
darauf auf. Schema bleibt eingefroren, neue Feature-Typen nur als Erweiterung.

## Future Architecture (Phase B2 bis F) — Notizen fuer spaeter

Diese Sektion haelt Konzepte fest, die NACH Phase 1 implementiert werden.
Reihenfolge und Details koennen sich aendern. Zweck: nichts geht verloren,
und Phase 1 wird nicht durch Zukunftsdetails verwaessert.

### Multi-Assembler (nach Phase 1)
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

### ContourSpecifier-Agent (Phase D)
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

### Spezialisten-Agents (bei Bedarf aufteilen, Phase D+)
Wenn der ContourSpecifier zu viele Sub-Faelle abdecken muss, weiter splitten:
Arc-Specifier, Sweep-Specifier, Revolve-Specifier. Jeder ein eigener 9b-Call.
Erst aufteilen, wenn ein einzelner Agent empirisch ueberfordert ist — nicht
vorsorglich.

### UI-Assembler-Tab (Face-Picking, nach Phase 1, vor Konturen)
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

### Modify-vs-neu Decider (nach Phase 1)
Heute muss der User die Datei abschliessen, bevor ein neues Teil
generiert wird. Deterministische Loesung:

- Leere Session oder expliziter "neu/reset"-Trigger → neu
- Aktives Teil + Keywords ("aendere", "fuege hinzu", "entferne", "an",
  "zusaetzlich") → modify
- Ein schmaler Pre-Schritt im entry_router, rein regelbasiert
- LLM-Fallback nur, wenn empirisch zu oft falsch entschieden

### Projekt-/Ordner-Agent (Phase F)
Autonome Struktur fuer mehrere Projekte:

- Thin LLM-Classifier: "neues Projekt?" vs. "in Projekt X ablegen?"
- Ordner-Erzeugung und Teile-Zuordnung
- Historie pro Projekt
- NICHT vor Phase 1 Abschluss bauen — organisatorisches Feature, kein
  Fortschritt am Kernproblem.

### Modification-Kontext (nach Phase 1)
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

### Training-Pairing (Good/Bad-Runs, nach Phase 1)
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

Jetzt nicht implementieren. Sobald Phase 1 Baseline steht und DSPy-Training
startet, wird das zur relevanten Datenquelle.

### DSPy-Training-Strategie
Am Ende Phase 1 einmaliges Baseline-Training:

- Jeder Prompt der 3-Step Chain separat (Inventar, Teil-Definierer, Assembly)
- PositionExtractor separat
- Reward-Signal aus Phase B Geometry Assertions (Delta zu erwartetem
  Volumen/BBox/Feature-Count)
- Kleine Datenmengen sind OK, solange Reward-Signal sauber ist
- Bei neuen Features/Modellen spaeter: Entscheidung pro Fall ob
  Weitertraining oder Neutraining mehr lohnt
- Vor Training: Schema muss eingefroren sein, sonst trainiert man auf
  Moving Target

## Bekannte Limitierungen

- CadQuery/OCCT: Non-manifold Tessellation bei flush-edge Unions
  → Workaround: 0.01mm Inset oder .clean() nach jeder Union
- Kleine Modelle (9b): Versagen bei raeumlichem Reasoning ohne Think-Modus
- Validator (LLM): Sagt oft "valid" bei offensichtlichen Fehlern
  → Wird durch deterministische Geometry Assertions ersetzt (Phase B)
- Fix-Loop: KI gibt manchmal resolved statt semantic Format zurueck
  → Resolver handhabt das jetzt (orientation wird trotzdem angewandt)