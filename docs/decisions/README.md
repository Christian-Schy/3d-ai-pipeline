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
