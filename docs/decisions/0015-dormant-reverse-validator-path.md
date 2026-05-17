# ADR 0015 — Dormanter Reverse-Validator-Pfad

- **Datum:** 2026-05-17
- **Status:** accepted
- **Verwandt:** ADR 0006, ADR 0014

## Kontext

Der bisherige finale `ValidatorAgent` kombiniert mehrere Aufgaben:
Geometrie-Checks, Volumen-/BBox-Plausibilitaet und semantische Bewertung
gegen die Spezifikation. Das ist fuer kleine Modelle riskant: wenn ein
Validator gleichzeitig Bohrungen, Nuten, Taschen, Positionen, Anker und
Textabsicht beurteilen soll, entsteht genau die Ueberladung, die ADR 0014
im Planungs-/Klassifizierer-Pfad abbaut.

Gleichzeitig ist die Zielrichtung richtig: Nach der Erstellung soll die
Pipeline rueckwaerts pruefen, welche Geometrie tatsaechlich entstanden ist,
und diese Ist-Fakten gegen Blueprint und User-Intent vergleichen.

## Entscheidung

Ein neuer, **dormanter** Reverse-Validator-Pfad wird vorbereitet:

```text
PipelineState / Blueprint / geometry_state / validator_stats
  -> structured fact extraction
  -> narrow deterministic checks
  -> non-blocking reverse validation report
```

Der Pfad liegt in `src/validation/` und ist **nicht** in
`src/graph/pipeline.py` oder `src/graph/edges.py` verdrahtet.

Grundregeln:

- Textverstaendnis bleibt LLM-Aufgabe.
- Deterministische Checks lesen nur strukturierte Artefakte.
- Kein Regex auf rohen User-Text.
- Jeder Check beantwortet eine kleine Frage.
- `unknown` ist ein echter Status und niemals ein verstecktes `passed`.
- Reports enthalten Evidenz: Quelle, Pfad, erwarteter Wert, beobachteter Wert.
- Das Scaffold ist nicht blockierend (`blocking_enabled=False`) und nicht
  graph-integriert (`graph_integrated=False`).

## Erster Umfang

Implementiert als inaktiver Startpunkt:

- `src/validation/contracts.py` — stabile Report-/Evidence-Contracts.
- `src/validation/fact_extraction.py` — strukturierte Fakten aus Feature-Tree,
  CSG-Tree, `geometry_state`, `validator_stats`, Code.
- `src/validation/reverse_validator.py` — nicht-gating Orchestrator.
- `src/validation/checks/feature_count.py` — interne Feature-/Build-Order-
  Konsistenz ohne Text-Parsing.
- `src/validation/checks/bbox.py` — einfache Root-BBox gegen beobachtete
  Extents.
- `src/validation/checks/volume.py` — konservativer Root-Volumencheck;
  bei subtraktiven Features `unknown` statt falscher Sicherheit.
- `src/validation/checks/feature_family.py` — Hole/Slot/Pocket-Familien
  bewusst `unknown`, bis echte Ist-Geometrie-Extraktion existiert.

## Verworfene Alternativen

1. **Direkt in den aktiven Graphen integrieren.** Verworfen, weil ADR 0014
   gerade Stabilitaet und klare Gates priorisiert. Ein neuer Validator darf
   nicht ungetestet echte Runs beeinflussen.
2. **Monolithischen Validator erweitern.** Verworfen, weil das die
   Ueberladungs-Klasse verschlimmert.
3. **Deterministische Textauswertung fuer Feature-Count.** Verworfen.
   "Was meint der User?" ist offenes Vokabular und bleibt LLM-Sache.

## Konsequenzen

- Der aktive Pipeline-Pfad bleibt unveraendert.
- Der neue Pfad kann in Tests, Debug-Scripten oder spaeterem Shadow-Mode
  manuell aufgerufen werden.
- Neue Checks koennen additiv eingebaut werden, ohne `PipelineState` oder
  Graph-Routing zu aendern.
- Erst nach Component-Goldens und Shadow-Reports darf eine separate ADR die
  Aktivierung als echtes Gate vorschlagen.

## Aktivierungsbedingung

Vor jeder produktiven Aktivierung muessen mindestens diese Bedingungen gelten:

- Component-Tests fuer jeden aktivierten Check.
- Kein Check interpretiert rohen User-Text deterministisch.
- Hole/Slot/Pocket-Ist-Fakten kommen aus Geometrie-/Code-Artefakten oder
  explizit strukturiertem LLM-Output, nicht aus Freitext-Regex.
- Shadow-Mode zeigt wiederholbar niedrige False-Positive-Rate.
- Routing bei `disable_coder` und template-mode Fail-fast bleibt unveraendert.
