# ADR 0009 — pattern_classifier-Split in grid / circular / linear

- **Datum:** 2026-05-16
- **Status:** accepted (Code umgesetzt; Sub-Agents disabled bis Training +
  Heatmap-Adoption)
- **Vorgaenger-ADRs:** 0006 (Klassifizierer-Split), 0008 (Capability-Matrix)
- **Verwandt:** Memory `project_grid_classifier_subagent.md`,
  `docs/conventions/24_pattern_din.md`, Golden `M_coverage_patterns_all_kinds`

## Problem

ADR 0006 hat den monolithischen `aktions_klassifizierer` in fuenf
typ-spezifische Sub-Klassifizierer zerlegt. Einer davon, der
`pattern_classifier`, traegt aber weiterhin **drei** unterschiedliche
Pattern-Familien in einem Prompt: Grid (Raster), Kreis (Lochkreis) und
Linear (Bohrungsreihe).

Konkret kann er "explizites Raster" (`Lochmuster NxM` + `Rasterabstand`
→ `rows`/`cols`/`spacing`) nicht zuverlaessig von "Eckbohrungen"
(`NxM Lochmuster` + `Randabstand` → `count`/`inset`) trennen. Ein
Retrain mit NxM-Traces (2026-05-16) hat `M_kombo` m02 regressiert — das
Eckbohrungs-2x2 wurde faelschlich als explizites Grid gelesen. Der
Retrain wurde zurueckgesetzt.

Folge: das L2-Coverage-Golden `M_coverage_patterns_all_kinds` blieb
**resolver-only** — die Grid-Geometrie (Schema `rows/cols/spacing`,
Template, Assembler, Resolver, Feature-Builder, Commit 33b288e) ist
gebaut + getestet, aber kein voller Pipeline-Golden moeglich, weil die
Klassifikation explizites Raster nicht erzeugt.

Gleicher Bug-Typ wie bei ADR 0006 (Klassifizierer) und beim Platzierer
(vor seinem Split): ein zu breiter Single-LLM-Call. Siehe Memory
`feedback_split_complex_agents` — lieber ein Agent mehr als ein
ueberladener Prompt.

## Entscheidung

Den `pattern_classifier` analog ADR 0006 in **drei** Pattern-typ-
spezifische Sub-Klassifizierer zerlegen. `pattern_classifier` entfaellt.

| Sub-Agent | Zustaendig fuer | Schluessel-Hints |
|---|---|---|
| `grid_classifier` | Raster-Lochmuster + Eckbohrungen | `rows`, `cols`, `rasterabstand`, `rasterabstand_x/_y`, `anzahl`, `abstand_kante` |
| `circular_classifier` | Lochkreis / Teilkreis | `anzahl`, `kreis_durchmesser` |
| `linear_classifier` | Bohrungsreihe / Lochreihe | `anzahl`, `abstand`, `richtung` |

Der `grid_classifier` traegt die Kern-Regel: **Rasterabstand genannt →
explizites Raster (`rows`/`cols`/`rasterabstand`); nur Randabstand →
Eckbohrungen (`anzahl`/`abstand_kante`, nie `rows`/`cols`)**. Der
`feature_builder` waehlt darueber den expliziten vs Legacy-Grid-Branch.

### Routing

Geschlossenes Keyword-Vokabular, gespiegelt in Runtime
(`detect_classifier_subagent`, `planning_action_nodes.py`) und
Trace-Projektion (`classifier_sub_agent_name_for_pair`,
`agent_contracts.py`):

- `lochmuster|lochbild|raster|grid|eckbohr*|an jeder ecke` → grid
- `lochkreis|teilkreis|kreismuster` → circular
- `bohrungsreihe|lochreihe|reihe aus|bohrungen entlang|...` → linear

Mehrdeutigkeit (mehrere Familien in einer Phrase) → Fallback auf den
monolithischen Klassifizierer.

### typ bleibt grob

Wie bei `pattern_classifier`: alle drei emittieren `typ="bohrung"`. Der
Normalizer verfeinert die Pattern-Familie (`lochkreis`/`eckbohrungen`/
`bohrungsreihe`) und `_reconcile_typ` haelt das innerhalb der
`bohrung`-Familie. Das explizite-Raster-Wording wurde additiv im
Normalizer-Prompt + in Normalizer-Demos ergaenzt.

## Konsequenzen

### Vorteile

- Pro-Pattern-Prompts knapp und fokussiert; der grid_classifier kann die
  Raster-vs-Eckbohrungs-Unterscheidung explizit lehren.
- `M_coverage` wird voller Pipeline-Golden (`pipeline/specs.txt`).
- Additiv: neue Pattern-Typen kommen als weitere Sub-Agents dazu.

### Risiken & Gegenmittel

- Dispatcher-Fehler → Fallback auf Monolith.
- Untrainierte Sub-Agents → starten `*_enabled: false`; erst nach
  Training + Heatmap-Diff (inkl. M_kombo-Regressions-Check) auf `true`.

### Adoptions-Sequenz

1. `train_dspy.py --agent grid_classifier` (analog circular/linear).
2. `config/config.yaml`: `grid_enabled`/`circular_enabled`/
   `linear_enabled` auf `true`.
3. `make goldens-real-filter F=M` — `M_coverage` muss gruen werden,
   `M_kombo` darf nicht regressieren.

## Verworfen

- **Nur `grid_classifier`, `pattern_classifier` behaelt Kreis+Linear** —
  liesse den Prompt zweifach belegt; der Split ist sauberer komplett.
- **Klassifizierer emittiert spezifischen typ** (eckbohrungen/lochkreis/
  bohrungsreihe statt `bohrung`) — groesserer Eingriff in `_reconcile_typ`
  und alle Pattern-Traces; nicht noetig, da der Normalizer die Familie
  ohnehin verlaesslich verfeinert (M_kombo gruen).
