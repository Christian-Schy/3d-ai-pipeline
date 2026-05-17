# ADR 0013 — NormalizerAgent-Split in typ-spezifische Sub-Normalizer

- **Datum:** 2026-05-17
- **Status:** superseded by ADR-0014 — der Normalizer wird nicht gesplittet,
  sondern eliminiert (seine Aufgaben wandern in die Klassifizierer). Siehe
  ADR 0014, Prinzip 3.
- **Vorgaenger-ADRs:** 0003 (Pro-Aktion-Mikro-Calls), 0006 (Klassifizierer-
  Split), 0009 (Pattern-Klassifizierer-Split)
- **Verwandt:** Memory `pipeline-structure-audit-2026-05-17` (Phase 2),
  `phase1-status-2026-05-17`, `feedback_split_complex_agents`,
  `feedback_determinism_scope`, Goldens `T_coverage`, `N_coverage`,
  `T_kombo`

## Problem

Der `NormalizerAgent` (`src/agents/normalizer_agent.py`, 545 LOC,
Prompt `prompt_normalizer.py` 349 Zeilen) ist ein einziger LLM-Call,
der **alle** Feature-Typen normalisiert (tasche, nut, bohrung,
lochkreis/eckbohrungen/bohrungsreihe, fase, rundung, aushoelung).

`NormalizerAgent.normalize(beschreibung, …)` bekommt den **Roh-Text**
der Phrase und re-parsed ihn unabhaengig vom Klassifizierer. Das ist
der Wartungs-Bottleneck und Quelle von Prompt+Demo-Drift.

Die Phase-1-Heatmaps 2026-05-17 haben **zwei konkrete Bugs** ueber
Traces nachgewiesen — beide im Normalizer-LLM, nicht im Klassifizierer:

1. **`versatz_*`-Doppel-Emit (bricht t08).** Phrase "in der oberen
   rechten Ecke 22mm nach links und 18mm nach unten versetzt". Der
   `pocket_classifier` liefert korrekt `abstand_rechts:22,
   abstand_oben:18`. Der Normalizer liest "… versetzt" zusaetzlich
   woertlich und emittiert `versatz_links:22 / versatz_unten:18` →
   `feature_builder` baut daraus ein bogus `center_offset` zusaetzlich
   zu den korrekten `edge_distances` → Resolver zaehlt doppelt.
   Symptom: `T_coverage` t08 + `T_kombo` t08 rot. Ein *korrekterer*
   Klassifizierer legt diesen Bug erst frei.

2. **`anfang_*/ende_*` verworfen (bricht n04).** Der `slot_classifier`
   liefert korrekt `anfang_links:20, ende_links:80`. Der Monolith-
   Normalizer-Prompt kennt die Keys nicht → re-parsed ohne sie →
   `feature_builder._resolve_slot_endpoints` sieht nie Rohwerte →
   `laenge` bleibt unaufgeloest. Symptom: `N_coverage` n04 rot.

Beide Bugs sind dieselbe Klasse wie ADR 0006/0009: ein zu breiter
Single-LLM-Call, dessen Verhalten beim Retrain wandert (Dev-Score
steigt, Pipeline regressiert — `feedback_dspy_retraining_discipline`).

## Entscheidung

Den `NormalizerAgent` analog ADR 0006/0009 in **fuenf** typ-Familien-
spezifische Sub-Normalizer zerlegen. Der monolithische `NormalizerAgent`
bleibt als Fallback bestehen.

| Sub-Normalizer | Zustaendig fuer typ | Kern-Fix |
|---|---|---|
| `pocket_normalizer` | tasche, aushoelung | kein `versatz_*` wenn `abstand_*` schon aus Ecke kommt (Bug 1) |
| `slot_normalizer` | nut | `anfang_*/ende_*` roh durchreichen (Bug 2) |
| `pattern_normalizer` | lochkreis, eckbohrungen, bohrungsreihe | Pattern-Familien-Verfeinerung + explizites Raster |
| `hole_normalizer` | bohrung | edge-to-center-Konvention |
| `edge_feature_normalizer` | fase, rundung | Kanten-Auswahl-Vokabular |

### Routing

**Trivial — kein Phrase-Regex noetig** (anders als beim ersten
Klassifizierer-Split). Der Klassifizierer hat `klassifikation.typ`
schon entschieden; der `feature_definierer`-Node routet deterministisch
nach `typ`-Familie an den passenden Sub-Normalizer. Unbekannter typ
oder disabled Sub-Normalizer → Fallback auf den Monolith-`NormalizerAgent`.

### Demos

`normalizer_traces.py` wird per Adapter pro Familie gefiltert (analog
`_adapter_hole_classifier` in `agent_contracts.py`). Die bestehenden
T06/T08/T12/N04/M06/M07/M09-Normalizer-Demos landen automatisch im
richtigen Sub-Normalizer-Trainset.

### Die zwei Bugs

Der Split fixt die Bugs nicht automatisch — er macht die Fixes sauber:
- `pocket_normalizer`-Prompt: explizite Regel "Ecke + bereits als
  `abstand_*` erfasster Versatz → KEIN zusaetzliches `versatz_*`".
- `slot_normalizer`-Prompt: `anfang_*/ende_*` als bekannte Keys,
  unveraendert durchreichen (Arithmetik macht `feature_builder`).

## Konsequenzen

### Vorteile

- Pro-Typ-Prompts knapp und fokussiert; jeder Sub-Normalizer lernt
  nur sein Vokabular — Stabilitaet beim Retrain.
- Phase-1-Goldens (`T_coverage`, `N_coverage`, `T_kombo`) werden gruen.
- Additiv: neue Feature-Typen kommen als weitere Sub-Normalizer dazu.

### Risiken & Gegenmittel

- Routing-Fehler → Fallback auf Monolith.
- Untrainierte Sub-Normalizer → starten `*_enabled: false`; erst nach
  Training + Heatmap-Diff einzeln auf `true`. Solange disabled, laeuft
  der Monolith — bricht garantiert nichts.

### Adoptions-Sequenz (pro Sub-Normalizer einzeln)

1. `train_dspy.py --agent <sub>_normalizer`.
2. `config/config.yaml`: `<sub>_normalizer_enabled` auf `true`.
3. `make goldens-real-filter F=<betroffene Goldens>` — Heatmap-Diff,
   keine Regression auf vorher-gruenen Specs.
4. Erst dann der naechste Sub-Normalizer.

Reihenfolge nach Leverage: `pocket_normalizer` + `slot_normalizer`
zuerst (sie tragen die zwei nachgewiesenen Bugs).

## Verworfen

- **Gezielter Patch am Monolith-Prompt** (nur die zwei Bugs im
  349-Zeilen-Prompt fixen) — wuerde Phase 1 schneller gruen machen,
  laesst aber den Wartungs-Bottleneck und den Retrain-Wander bestehen.
  Bewusst zugunsten der Stabilitaet verworfen: wenn der Bottleneck
  ohnehin identifiziert ist, ihn gleich strukturell aufloesen.
- **Klassifizierer reicht Hints unveraendert an `feature_builder`,
  Normalizer entfaellt** — der Normalizer leistet echtes Textverstaendnis
  (offenes Vokabular: Anker-Phrasen, Synonyme, Mehrdeutigkeit), das der
  Klassifizierer pro Phrase nicht abdeckt. Nicht streichbar, nur
  splittbar.
