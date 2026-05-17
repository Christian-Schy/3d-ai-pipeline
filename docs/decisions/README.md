# Architecture Decision Records (ADRs)

Hier liegen die architektonischen Entscheidungen des Projekts. Eine ADR
dokumentiert pro Datei: **Kontext** (Problem), **Entscheidung** (was), die
**verworfenen Alternativen** und die **Konsequenzen**.

Ziel: spaeter (in 3 Monaten, 12 Monaten oder beim naechsten Eigentuemer-
Wechsel) ist nachvollziehbar **warum** etwas so gebaut wurde, nicht nur **was**.
ADRs sind nicht versionsbezogen und sollten nach Annahme nicht mehr stark
veraendert werden — wenn eine Entscheidung revidiert wird, schreibe eine
neue ADR und verweise von der alten auf die neue.

Was ein ADR-Eintrag bekommt: keine Implementierungs-Details, keine
Zeilennummern (driften), aber sehr wohl Datei-Pfade und Funktions-Namen.

Was ADR nicht sind: keine Bug-Fix-Reports (das ist `CHANGELOG.md`), kein
Tagebuch, keine User-Doku.

## Numerierung

Vierstellig fortlaufend, kein Datum im Dateinamen. Erste ADR = `0001-...`.
Wenn eine ADR ersetzt wird, wird der Status auf "superseded" gesetzt und ein
Verweis auf die neue ADR ergaenzt.

## Status-Werte

- **proposed** — Vorschlag, noch nicht implementiert
- **accepted** — implementiert und produktiv
- **superseded by ADR-XXXX** — durch eine neuere ADR ersetzt
- **deprecated** — nicht mehr gueltig, aber bisher kein Ersatz

## Verzeichnis

| ADR | Status | Titel |
|---|---|---|
| [0001](0001-pocket-child-placer-mapping-only.md) | accepted | pocket_child_placer macht nur Containment-Mapping, nicht Position-Parsing |
| [0002](0002-plan-validator-pocket-floor-filter.md) | accepted | plan_validator filtert pocket_floor depth-Errors deterministisch |
| [0003](0003-inventar-feature-definierer-pro-aktion.md) | proposed | Inventar + feature_definierer auf Pro-Aktion-Mikro-Calls |
| [0004](0004-bug7-bug8-anchor-edge-and-splitter-feed.md) | accepted | Bug7/Bug8 Anchor-Edge-Konvention + Splitter-Feed |
| [0005](0005-regressions-baseline-feature-matrix.md) | accepted | Regressions-Baseline + Feature-Matrix vor weiterer Architektur-Arbeit |
| [0006](0006-classifier-split-and-future-splits.md) | accepted | Klassifizierer-Split in Sub-Agents (hole/pocket/slot/pattern/edge) |
| [0007](0007-inventar-step-a-pro-teil-chunking.md) | accepted | Inventar Step A Pro-Teil-Chunking fuer Multi-Part-Specs |
| [0008](0008-capability-coverage-matrix-structure.md) | accepted | Capability×Coverage Matrix als Projekt-Struktur (ersetzt lineare Phasen) |
| [0009](0009-pattern-classifier-split-grid-circular-linear.md) | accepted | pattern_classifier-Split in grid/circular/linear Sub-Agents |
| [0010](0010-a5-anchor-classifier-hint.md) | zurueckgezogen | A5-Anker-Hint verworfen — A5 ist konventionell A1 bzw. A2 |
| [0011](0011-slot-endpoint-model.md) | accepted | Slot Anfangs-/Endpunkt-Modell (anfang_*/ende_*), Code rechnet laenge |
| [0012](0012-pattern-rotation.md) | accepted | Pattern-Rotation (Grid + Linear) ueber Template-angle-Parameter |
| [0013](0013-normalizer-split.md) | superseded by ADR-0014 | NormalizerAgent-Split — verworfen, Normalizer wird eliminiert statt gesplittet |
| [0014](0014-pipeline-rebuild-clean-architecture.md) | proposed | Pipeline-Rebuild: Clean Per-Action Architecture (Master-Umbau-Plan) |
