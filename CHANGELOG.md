# Changelog

Chronologische Liste nennenswerter Aenderungen am Projekt. Pro Eintrag der
Commit-Hash, eine Kurzbeschreibung und (wenn vorhanden) ein Verweis auf die
zugehoerige ADR unter `docs/decisions/`.

Architektur-Entscheidungen liegen als ADRs (Architecture Decision Records)
in `docs/decisions/` — dort steht das **Warum** zu jeder grundlegenden
Aenderung. Hier in der Changelog steht das **Was** mit Datum.

## 2026-05-06

- **Quick Wins fuer Stufe 5c** — zwei kleine Aenderungen aus der
  Real-Run-Analyse von Run 3c0212ae:
  - `agent_options.normalizer.think=false` (config.yaml). Im neuen Pfad
    hat der Aktions-Klassifizierer (Stufe 2) typ/seite/parameter_hints
    bereits extrahiert; der Normalizer parst nur noch position/richtung
    /Versatz-Details. Reasoning ist da Overkill und kostet 8-16s/Call.
    Erwarteter Effekt: feature_definierer-Latenz von ~16s/Call auf
    2-4s/Call.
  - Klassifizierer-Prompt um Rotations-Vorzeichen-Konvention erweitert:
    "im Uhrzeigersinn" → negativ, "gegen Uhrzeigersinn" → positiv
    (CadQuery-CCW-positiv-Konvention). Plus zwei neue Few-Shot-
    Beispiele die genau diese Faelle zeigen. Run 3c0212ae hatte 4 von
    8 rotierten Taschen mit falschem Vorzeichen (alle "im
    Uhrzeigersinn"-Faelle wurden als +20 statt -20 klassifiziert).

- **Pipeline-Verdrahtung (Stufe 5b von ADR 0003)** — die in Stufe 5a
  vorbereiteten Per-Aktion-Nodes sind jetzt im LangGraph aktiv.
  Aenderungen am Graph:
  - `inventar_node` ruft auf fresh runs `extract_teile_only()` (Step A
    only). Retry-Pfad mit validator_feedback bleibt auf legacy
    `extract()` damit Teil-Dimensions-Korrektur weiter funktioniert.
  - Neue Edges: `inventar → aktions_splitter → aktions_klassifizierer
    → text_splitter → position_extractor → feature_definierer →
    aktions_aggregator → platzierer`. Damit ersetzt die deterministische
    Splitter+Klassifizierer-Kombi den verklumpenden Inventar-Step-B.
  - `feature_definierer_node` umgestellt auf
    `NormalizerAgent.define_feature(klass, teil)`. Eingabe sind die
    `aktions_klassifikationen` aus Stufe 2; Ausgabe sind `aktions_features`
    mit `_teil_id / _phrase_idx / _parent_phrase_idx`-Markern. Ueberlebt
    einzelne Klassifikationen ohne Teil-Zuordnung mit Warning.
  - `aktions_aggregator_node` ist jetzt der Producer von
    `teil_definitionen` (deterministisch). Nested Bohrung-in-Tasche
    bekommt parent=tasche_id ohne dass `pocket_child_placer` noch das
    LLM bemuehen muesste — der bleibt aber als Sicherheitsnetz im Graph.
  - Initial-State init in pipeline.py um die neuen Felder ergaenzt.
  - Modify/Error-Loop-Pfad ueber `blueprint_architect` ist unangetastet.
  - Graph compiliert sauber (27 Nodes, +3 ggue. Stufe 5a). Suite weiter
    217/217 gruen. Real-Run-Verifikation (Stufe 5c / ADR Stufe 6) folgt
    separat — dort wird auch `agent_options.normalizer.think=false`
    gegen die Latenz pruefen.

- **Pipeline-Vorarbeit (Stufe 5a von ADR 0003)** — alles additiv, noch
  kein Graph-Wiring. Vorbereitet:
  - `InventarAgent.extract_teile_only(specification)` liefert die Step-A-
    Teile-Liste OHNE den verklumpenden Step B (aktionen=[] explizit).
    Die alte `extract()` bleibt fuer Modify/Error-Loop-Pfad unangetastet.
  - PipelineState bekommt drei neue Felder:
    `aktions_phrases`, `aktions_klassifikationen`, `aktions_features`.
  - Drei neue Node-Wrapper in [src/graph/nodes/planning_nodes.py]:
    `aktions_splitter_node` (deterministisch), `aktions_klassifizierer_node`
    (LLM-Loop), `aktions_aggregator_node` (deterministisch). Alle drei
    emittieren agent_traces und sind ueber `src.graph.nodes` exportiert.
    NOCH NICHT in den Graph eingehaengt — Stufe 5b verdrahtet.
  - Klassifizierer-Node reicht parent_phrase fuer nested Children durch
    (so dass Stufe 2 die seite vom Parent erben kann), ueberlebt einzelne
    classify-Exceptions ohne den Loop abzubrechen.
  - 11 Node-Tests + 4 Tests fuer extract_teile_only — alle gruen.
  - Suite weiterhin 217/217 gruen.

- **Aktions-Aggregator (Stufe 4 von ADR 0003)** — neuer deterministischer
  Modul `src/tools/aktions_aggregator.py`. `aggregate(features, teile)`
  baut die finale `teil_definitionen[]`-Struktur aus den Pro-Aktion-
  Features von `define_feature` (Stufe 3). Gruppiert nach `_teil_id`,
  sortiert per `_phrase_idx` (Spec-Reihenfolge), loest `_parent_phrase_idx`
  in die Parent-Feature-ID auf (das fixt deterministisch den
  Verschachtelungs-Pfad: Bohrung in Tasche kriegt jetzt `parent=tasche_*`
  statt `parent=teil_id`). Strippt interne Marker im Output, damit das
  Schema 1:1 zum heutigen `build_teil_definition`-Output passt.
  Orientation aus `teil.beschreibung` (gleiche Heuristik wie heute:
  hochkant / flach / standard). Dangling parent_phrase_idx faellt auf
  `teil_id` zurueck und loggt. 16 Unit-Tests gruen. End-to-End-Smoke der
  ganzen Stufe 1+2+3+4-Kette auf 2 Tasche+Bohrung-Paaren liefert eine
  korrekte `teil_definitionen[]` mit aufgeloesten parent-Verweisen.
  Standalone-Modul — Pipeline-Wiring folgt in Stufe 5.

  Nebenaenderung in [src/agents/normalizer_agent.py]: `define_feature`
  setzt jetzt zusaetzlich den `_teil_id`-Marker, damit der Aggregator
  features auch nach parent-Rewrite korrekt gruppieren kann.

- **Toten Test-Code entfernt** — 4 Test-Files mit collect-errors auf
  geloeschte Module raus (`test_planner_diff.py`, `test_prompt_assembler.py`,
  `test_feature_tagger.py`, `tests/graph/` komplett — der conftest dort
  importierte 3 nicht mehr existierende Agents). Plus 7 stale Tests in
  `test_config.py` (referenzierten `models.planner_*`) und 1 Assert in
  `test_function_decomposer.py` (testete altes code_skeleton-Verhalten).
  Vorher: 10 fail / 13 collect-error. Jetzt: 202/202 gruen (ohne
  tests/golden/ — Ollama — und tests/test_app.py — eigener Bug
  `SessionState.last_run_id`).

- **feature_definierer-Refactor (Stufe 3 von ADR 0003)** — neue Methode
  `NormalizerAgent.define_feature(klassifikation, teil)` als Pro-Aktion-
  Eintrittspunkt. Eingabe: 1 klassifizierte Aktion (vom Aktions-
  Klassifizierer aus Stufe 2). Ausgabe: 1 SemanticFeature gemaess ADR-
  Schnittstellen-Vertrag, inklusive `_phrase_idx` und `_parent_phrase_idx`-
  Marker fuer den Aggregator (Stufe 4). `parent` defaultet auf die
  teil_id; der Aggregator ueberschreibt fuer nested Children (Bohrung in
  Tasche) mit der Pocket-Feature-ID. Type-Reconciliation respektiert
  Familien (Classifier `bohrung` + Normalizer `lochkreis` → Normalizer
  gewinnt; cross-family oder Normalizer `ignorieren` → Classifier
  gewinnt). Classifier-Seite trumpft Normalizer-Seite (Stufe 2 hat sie
  schon validiert / vom Parent geerbt). Hints aus Stufe 2 fuellen Luecken
  in `parameter` (rotation_deg → drehung Translation), ueberschreiben
  aber nicht was der Normalizer geparst hat. 17 Unit-Tests gruen.
  Live-Smoke (Splitter → Klassifizierer → define_feature) auf 2 nested
  Tasche+Bohrung-Paare laeuft strukturell korrekt, aber zeigt das alte
  Latenz-Problem: Normalizer mit Default `think=true` braucht ~60s/Call.
  Stufe 5 entscheidet ob `agent_options.normalizer.think=false` machbar
  ist (Aufgabe ist mit Pre-Klassifikation deutlich kleiner). Existing
  `normalize()` API bleibt unveraendert — Stufe 5 schaltet das Call-
  Site um.

- **Aktions-Klassifizierer (Stufe 2 von ADR 0003)** — neuer Agent
  `src/agents/aktions_klassifizierer.py` klassifiziert genau EINE Phrase
  vom Splitter in `{typ, seite, parameter_hints}`. Strukturelle Felder
  vom Splitter (`teil_id`, `phrase_idx`, `parent_phrase_idx`) werden 1:1
  durchgereicht; das LLM klassifiziert nur. Modell `gemma4:26b` mit
  `think=false`, `temperature=0.0` — Aufgabe ist trivial (5 Typen).
  Robust gegen defekte LLM-Outputs (unbekannter Typ → `"unbekannt"`,
  unbekannte Seite → `"oben"`, kaputtes parameter_hints → leeres Dict,
  LLM-Exception → Default-Klassifikation mit erhaltenen Splitter-Feldern).
  13 Unit-Tests gruen. agent_contracts.py-Adapter und config-Eintrag
  ergaenzt; aktiv geschaltet wird der Contract erst in Stufe 7
  (DSPy-Re-Training). Standalone — Pipeline-Integration in Stufe 5.

- **Aktions-Splitter (Stufe 1 von ADR 0003)** — neuer deterministischer
  Modul `src/tools/aktions_splitter.py` segmentiert die User-Spec in
  einzelne Aktions-Phrasen. Splittet an Komma, Seiten-Schluesselwoertern
  und Verschachtelungs-Markern (`in der Tasche`, `in der Ausnehmung`,
  `darin`, `innerhalb`). Verschachtelte Aktionen ("Bohrung in der
  Tasche") bekommen `parent_phrase_idx` gesetzt — der Verschachtelungs-
  Bug aus Run 6efaa489 (3 statt 6 Aktionen) und 14fa8d40 (16 statt 24)
  ist damit deterministisch geloest. 17 Tests gruen, davon 3 Reference-
  Runs aus dem ADR. Noch nicht in die Pipeline verdrahtet — Standalone-
  Modul, integriert wird in Stufe 5. Siehe
  [ADR 0003](docs/decisions/0003-inventar-feature-definierer-pro-aktion.md).

## 2026-05-05

- **plan_validator filtert pocket_floor depth-Errors deterministisch**
  (`ca15719`) — Check 6 hat false positives fuer Bohrungen produziert, die
  absichtlich durch den Taschenboden ins Material gehen. Der LLM-Validator
  hatte das nicht verstanden und einen vollen Retry-Cycle (~17s) ausgeloest.
  Loesung: Post-Filter wirft Errors raus, wenn das betroffene Feature
  `params.depth_reference_applied="pocket_floor"` traegt. Siehe
  [ADR 0002](docs/decisions/0002-plan-validator-pocket-floor-filter.md).

- **pocket_child_placer reicht Position vom feature_definierer durch**
  (`9393767`) — Bisher hat der Agent das LLM zweimal Position parsen lassen
  und dabei Versatz-Werte verloren (Run 965da548: "10mm nach oben"-Versatz
  ging verloren). Jetzt macht er nur noch Containment-Mapping (welche
  Bohrung in welche Tasche), die Position kommt 1:1 vom Upstream-Feature.
  Latenz 21s -> 6.4s. Siehe
  [ADR 0001](docs/decisions/0001-pocket-child-placer-mapping-only.md).

## 2026-05-04

- **per-Teil Labeler + Anker/Edge-Distanz Trainings-Cases** (`7eb3b93`) —
  position_extractor ist umgebaut zum per-Teil Labeler (placement vs feature),
  21 Trainings-Cases in `data/dspy_training/labeler_platzierer_traces.py`,
  `_parse_kv` akkumuliert Multi-Line-Keys.

- **consolidate pending in-flight work** (`5c4cf4b`) — Sammel-Commit
  fuer kleinere konsolidierte Aenderungen.

## 2026-05-03

- **rewrite 'Zur Entstehung' in personal voice** (`674975c`) — README-Sektion
  ueberarbeitet.

- **split function_decomposer into focused modules** (`57d97a0`) — Refactor:
  function_decomposer in fokussierte Untermodule zerlegt.

## 2026-05-01

- **prevent Coder-Crash on simple specs + train Inventar 'auf X-Seite' pattern**
  (`cc3ca86`) — Coder-Crash bei Simple-Specs verhindert, Inventar mit neuem
  Trainings-Pattern.

- **stable workplane origin via _ref-pattern (Centroid-Drift-Bug)**
  (`22f6ef0`) — Workplane-Origin stabilisiert.

- **alignment-upgrade darf edge_distances nicht ueberschreiben** (`a527ee1`)
  — Alignment-Upgrade-Logik korrigiert.

## 2026-04-30

- **wire DSPy-optimized demos into pipeline agents** (`ad5ce37`) — DSPy-
  optimierte Demos in Pipeline-Agents eingebunden.

- **align DSPy training targets with pipeline reality** (`863309d`) —
  Trainings-Targets an Pipeline-Realitaet ausgerichtet.

## 2026-04-28

- **DSPy training adapter for local LLMs** (`a3016f1`) —
  DSPy-Trainings-Adapter fuer lokale LLMs (think=False + JSONAdapter).

## Aelter

Fuer Aenderungen vor diesem Punkt siehe `git log` direkt.
