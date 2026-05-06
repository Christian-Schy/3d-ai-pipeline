# Changelog

Chronologische Liste nennenswerter Aenderungen am Projekt. Pro Eintrag der
Commit-Hash, eine Kurzbeschreibung und (wenn vorhanden) ein Verweis auf die
zugehoerige ADR unter `docs/decisions/`.

Architektur-Entscheidungen liegen als ADRs (Architecture Decision Records)
in `docs/decisions/` — dort steht das **Warum** zu jeder grundlegenden
Aenderung. Hier in der Changelog steht das **Was** mit Datum.

## 2026-05-06

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
