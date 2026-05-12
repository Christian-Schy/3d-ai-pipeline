# ADR 0006 — Klassifizierer-Split + nachfolgende Sub-Agent-Splits

- **Datum:** 2026-05-11
- **Status:** active (Phase A-C implementiert, Phase D: `hole_classifier` adoptiert)
- **Vorgaenger-ADRs:** 0003 (Pro-Aktion-Mikro-Calls), 0005 (Regressions-Baseline)
- **Verwandt:** Memory `project_split_pattern_candidates.md`,
  `project_klassifizierer_tasche_regress.md`

## Problem

Der `aktions_klassifizierer` ist heute ein monolithischer LLM-Call der pro
Phrase `{typ, seite, parameter_hints}` extrahiert — fuer alle Feature-Typen
(Bohrung, Tasche, Nut, Lochmuster, Fase, Rundung). Empirisch 2026-05-11:

- Aktivierung mit 78 kuratierten Pairs bringt **+B1 v2 PASS** (Wert-Swap
  Bug deterministisch fixbar)
- **Gleichzeitig -EF und -T_kombo** durch Cross-Contamination der
  Tasche-Demos mit anderen Feature-Typen → Netto -1 PASS

Zusaetzlich beobachtet: das Modell schwankt bei mehrdeutigen Tasche-Phrasen
(z.B. "deren rechte kante 25mm von rechter wuerfelkante") zwischen
edge-to-edge (`kante_rechts`) und edge-to-center (`abstand_rechts`)
Interpretation — pure LLM-Coin-Flip auf ein 26b-Modell ohne Stuetze.

Heatmap (`data/sessions/heatmap_20260511_210435.md`) zeigte **4 von 5
verbleibenden Fails als Klassifizierer-nahe Themen**: B1 v2 (Wert-Swap),
B_kombo_additive_anchor (Anker ging vor der Klassifikation verloren),
M_kombo (achse-Schema fehlt), T_kombo (kante/abstand Coin-Flip). In Phase D
stellte sich B_kombo_additive_anchor als Splitter-Verlust heraus: der
comma-getrennte Prefix `oben: obere rechte ecke ...` wurde verworfen, bevor
Normalizer/Resolver den Anchor sehen konnten.

**Gleicher Bug-Typ wie bei Platzierer (vor seinem Split):** ein zu breiter
Single-LLM-Call. Pattern hat sich beim Platzierer (Split in 4 Sub-Agents
2026-05-04) bewaehrt — er produziert seither stabile, isolierbare Outputs.

## Entscheidung

Den `aktions_klassifizierer` analog dem Platzierer in **5 typ-spezifische
Sub-Klassifizierer** zerlegen, additiv mit Fallback auf den monolithischen
Klassifizierer. Wenn das stabil laeuft, dasselbe Muster auf weitere
Agents (`plan_validator`, `normalizer`) anwenden.

### Sub-Klassifizierer-Bruchlinie

Mirror der `_TYP_MAP` aus `src/tools/feature_builder.py`:

| Sub-Agent | Zustaendig fuer (typ) | Output-Schema |
|---|---|---|
| `hole_classifier` | `bohrung` | `{seite, durchmesser, tiefe, abstand_*, versatz_*, kante_*}` |
| `pocket_classifier` | `tasche` | `{seite, laenge, breite, tiefe/hoehe, rotation_deg, abstand_*, versatz_*, kante_*}` |
| `slot_classifier` | `nut` | `{seite, laenge, breite, tiefe, richtung, rotation_deg, abstand_*, versatz_*, kante_*}` |
| `pattern_classifier` | `lochkreis`, `eckbohrungen`, `bohrungsreihe` | `{seite, durchmesser, tiefe, anzahl, kreis_durchmesser, abstand, abstand_kante, richtung, ...}` |
| `edge_feature_classifier` | `fase`, `rundung` | `{seite, kante, groesse}` |

`shell` (`aushoelung`) ist bisher selten — bleibt im Fallback bis es
empirisch relevant wird.

### Dispatch

Der Pipeline-Knoten `aktions_klassifizierer_node` bekommt einen leichten
Pre-Step: aus der Phrase deterministisch (Keyword-Match) den typ erkennen
(`bohrung`/`tasche`/...). Bei Mehrdeutigkeit oder Unbekanntem faellt er
auf den monolithischen Klassifizierer zurueck.

Pseudo-Code:

```python
TYP_KEYWORDS = {
    "bohrung": ("bohrung", "loch"),
    "tasche":  ("tasche", "ausnehmung", "ausfraesung"),
    "nut":     ("nut",),
    "lochkreis":      ("lochkreis", "teilkreis"),
    "eckbohrungen":   ("eckbohrungen",),
    "bohrungsreihe":  ("bohrungsreihe", "lochreihe", "reihe"),
    "fase":    ("fase",),
    "rundung": ("rundung", "fillet"),
}

def detect_typ(phrase: str) -> str | None:
    pl = phrase.lower()
    for typ, kws in TYP_KEYWORDS.items():
        if any(kw in pl for kw in kws):
            return typ
    return None
```

Auf Ambiguitaet (zwei Treffer): Fallback. Auf Treffer: route zum
typ-spezifischen Sub-Klassifizierer.

## Konsequenzen

### Vorteile

- **Pro-Typ-Demos isoliert** — Tasche-Demos verschmutzen nicht Bohrungs-
  Outputs (Cross-Contamination verschwindet, Tasche-Regress aus 2026-05-11
  wird systematisch geloest)
- **Pro-Typ-Prompts knapper** — jeder Sub-Prompt deckt nur seinen Typ.
  Aktuell ist `prompt_aktions_klassifizierer.py` lang und general; jede
  neue Regel macht ihn schlechter fuer andere Typen.
- **Additive Skalierung** — neue Feature-Typen (Phase 3 Connection, Loft,
  Sweep, Revolve) werden als neue Sub-Klassifizierer addiert ohne
  Bestehende zu beruehren.
- **Lock-In jetzt billiger als spaeter** — 70 Seed-Pairs heute lassen
  sich sortenrein aufteilen; bei 200+ Pairs in 6 Wochen ist Reorganisation
  teurer.

### Risiken & Gegenmittel

- **Dispatcher-Fehler** routet falsch → Fallback auf Monolith faengt das ab.
- **Zu wenig Demos pro Sub-Agent** anfangs → Heatmap-Diff zeigt unmittelbar
  ob ein Sub-Agent ready ist; sonst bleibt sein Fallback aktiv.
- **Trainingsdaten-Doppelpflege** → strikt: `klassifizierer_traces.py`
  ist die Quelle; Sub-Files werden daraus per Filter (`typ == "bohrung"`)
  erzeugt, nicht handgepflegt.

### Verworfen

- **Audit + Re-aktivierung des Monolith-Klassifizierers** — Aufwand pro
  Audit linear, Risk Cross-Contamination bleibt. Detail in
  `project_split_pattern_candidates.md`.
- **Conditional Activation per Typ** (Hack mit Per-Phrase-Demo-Filter) —
  fragil, vermischt Daten- und Agent-Logik.

## Umsetzung (additive Migration)

**Phase A — Kontrakte + Adapter (keine Runtime-Aenderung)**

Status 2026-05-11: **implementiert**. `train_dspy.py --stats` zeigt:
`hole_classifier` 27 Pairs, `pocket_classifier` 24, `slot_classifier` 14,
`pattern_classifier` 10, `edge_feature_classifier` 10. Im ersten Schritt
blieben alle fuenf `active=False`; nach Phase D ist `hole_classifier` der
erste aktive Sub-Contract. `aktions_klassifizierer` bleibt der Runtime-
Fallback.

1. In `data/dspy_training/agent_contracts.py` fuenf neue `AgentContract`-
   Eintraege (`hole_classifier` ... `edge_feature_classifier`), jeweils
   `active=False` im ersten Schritt.
2. Fuenf neue `_adapter_*_classifier`-Funktionen — projizieren aus den
   bestehenden Klassifizierer-Traces nur die Eintraege ihres Typs.
3. `klassifizierer_traces.py`: Quelle bleibt ein File; Filter passiert im
   Adapter. Drei Pattern-Seeds wurden ergaenzt, damit `pattern_classifier`
   die Mindestbasis von 10 Pairs erreicht.
4. `train_dspy.py --stats` zeigt fuenf neue Zeilen mit Pair-Counts pro Typ.
   Nach dem Coverage-Audit am 2026-05-12 decken Pattern-Seeds explizit
   `anzahl`, `kreis_durchmesser`, `abstand` und `abstand_kante`; Slot-Seeds
   decken `rotation_deg`; Pocket-`hoehe` wird downstream als `tiefe`
   normalisiert.

**Phase B — Sub-Agent-Implementierung**

Status 2026-05-11: **implementiert**. Neuer Runtime-
Codepfad in `src/agents/classifier_sub_agents.py`, eigene Prompt-Dateien
`data/prompts/prompt_classifier_{hole,pocket,slot,pattern,edge_feature}.py`
und eigene DSPy-Signatures/Module in `train_dspy.py`. Die Sub-Agenten liefern
weiterhin das ADR-0003-kompatible Ergebnis `{typ, seite, parameter_hints}`,
damit Phase C nur dispatchen und fallbacken musste.

5. Neuer Code-Pfad in `src/agents/classifier_sub_agents.py` (oder
   gleichwertig) der pro Sub-Agent einen call macht. Eigene Prompt-Datei
   pro Sub-Agent in `data/prompts/prompt_classifier_<typ>.py`.
6. Initial: Prompts sind enge Auszuege aus dem heutigen
   `prompt_aktions_klassifizierer.py` (nur Tasche-Regeln im Tasche-Prompt etc).

**Phase C — Dispatcher + Fallback in Runtime**

Status 2026-05-11: **implementiert, initial Flags default false**. Der Node nutzt
`detect_classifier_subagent(phrase)` in `planning_action_nodes.py`, routet
nur bei eindeutigem Treffer und aktiviertem Flag
`classifier_subagents.<typ>_enabled`. Bei deaktiviertem Flag, Ambiguitaet
oder Sub-Agent-Fehler faellt er auf `AktionsKlassifizierer` zurueck. Die
Trace-Ausgabe enthaelt `routes`, damit Heatmaps spaeter sehen, welcher Pfad
benutzt wurde. Initial liess die Default-Config alle Flags auf `false`,
damit Runtime bis zur Phase-D-Adoption identisch blieb.

7. `aktions_klassifizierer_node` bekommt:
   - `detect_typ(phrase)` als deterministischen Pre-Step
   - Routing zu `<typ>_classifier`-Agent wenn typ erkannt UND Sub-Agent
     aktiviert (per Feature-Flag z.B. `classifier_subagents.hole_enabled`)
   - Fallback auf bestehenden Klassifizierer sonst
8. Aktivierungen kommen einzeln in Phase D, je Sub-Agent eine Heatmap-
   Iteration: trainieren, Flag setzen, Heatmap-Diff, adopt-oder-rollback.

**Phase D — Klein-Bestaetigungs-Zyklus pro Sub-Agent**

Status 2026-05-11: **`hole_classifier` adoptiert**.

Der `hole_classifier` wurde separat trainiert:

- Trainingsbasis: 27 Pairs (`6` Trace + `21` Seed), Train `21`, Dev `6`.
- DSPy-Ergebnis: Dev-Score `0.90`, Artefakt
  `data/dspy_optimized/hole_classifier_optimized.json` mit 8 Demos. Dieses
  adoptierte Artefakt ist gezielt aus dem sonst ignorierten
  `data/dspy_optimized/` ausgenommen, damit `hole_enabled: true` im
  oeffentlichen Git reproduzierbar ist.
- Feature-Flag: `classifier_subagents.hole_enabled: true`; DSPy-Contract
  `hole_classifier.active=True`.
- Gate: `.venv/bin/python -m scripts.run_real_goldens --filter B --no-persist --no-jsonl`
  -> `11 PASS / 0 FAIL`.

Im selben Zyklus wurde `B_kombo_additive_anchor` stabilisiert: der
deterministische Splitter puffert jetzt comma-getrennte Corner-Anchor-
Praefixe und haengt sie an die folgende Feature-Phrase. Neue
Component-Golden:
`tests/golden/components/B_kombo_additive_anchor/splitter/`.

Cross-Family-Smoke:
`.venv/bin/python -m scripts.run_real_goldens --filter EF,T,NEST,M --first-only --no-persist --no-jsonl`
-> `EF` PASS, `NEST` PASS, `M` FAIL (bestehender Pattern/Splitter-
Feature-Count), `T` FAIL (bestehender Pocket/Resolver-kante-vs-abstand-
Pfad). Diese Fails blockieren den Hole-Rollout nicht, bleiben aber die
naechsten separaten Sub-Agent-/Deterministik-Themen.

Fuer die uebrigen Sub-Agenten gilt weiter: trainieren, Flag setzen,
Heatmap-Diff, adoptieren oder rollbacken.

**Phase E — Monolith-Abloesung (am Ende)**

9. Wenn alle 5 Sub-Klassifizierer adoptiert sind und der Fallback in 100%
   der Real-Runs nicht mehr feuert: monolithischen Klassifizierer-Pfad
   entfernen, `aktions_klassifizierer` Contract auf `active=False`
   gepinnt mit Deprecation-Kommentar.

## Was danach im gleichen Prinzip folgt

Reihenfolge nach Impact:

### 1. `plan_validator` (Phase-1-Punkt-6 Roadmap)

Splitten in pro-Aspekt-Validatoren:

- `position_validator` (sind alle Features auf der korrekten Face?)
- `rotation_validator` (Drehungen plausibel und konsistent mit Spec?)
- `face_validator` (haben Multi-Face-Specs alle erwarteten Faces belegt?)
- `anchor_validator` (sind Anker-Strukturen korrekt aufgeloest?)
- `feature_count_validator` (deterministisch — zaehlt Features in BP gegen
  Spec-Phrasen)

Plus eigene **deterministische Geometry-Assertions** (Phase B Teil 2 der
Roadmap):

- Volumen-Erwartung aus resolved BP vs. Executor-Output, Delta > 5% Fehler
- BBox-Erwartung
- Feature-Count

Diese Asseertions ersetzen langfristig die unzuverlaessigen LLM-
Validierungen.

### 2. `normalizer` (per-Feature-Typ-Split)

Heute monolithisch, gleiche Cross-Contamination-Risiken wie Klassifizierer
(durchmesser-vs-laenge-vs-radius-Konflikte). Split nach derselben
Bruchlinie (`hole_normalizer`, `pocket_normalizer`, ...) oder direkt mit
dem Klassifizierer-Split zusammengelegt (Klassifizierer liefert schon
das normalisierte Output-Schema seines Typs — Normalizer wuerde
redundant).

**Empfehlung:** im Zuge des Klassifizierer-Splits pruefen, ob der
Normalizer als separater Schritt noch noetig ist oder vom Sub-Klassifizierer
direkt mit-erledigt werden kann. Wenn redundant: entfernen statt splitten.

### 3. `feature_definierer` (langfristig, ab Phase 3)

Heute mehrheitlich deterministisch ueber `feature_builder.build_feature`.
Wenn Phase 3 (Loft, Sweep, Revolve, Connection) kommt, wird die
deterministische Bau-Logik komplex pro Typ — dann zweiteilen in
`feature_assembler_box` (Bohrung, Tasche, Nut) und neue Assembler pro
komplexem Typ (siehe CLAUDE.md "Multi-Assembler").

### 4. `position_extractor` (niedrige Prio)

Heute durch deterministischen Post-Filter (`_relabel_features_on_self`,
2026-05-11) ausreichend stabilisiert. Split waere optional, kein
akuter Need.

## Erfolgsmessung

- **Pro Sub-Agent Activation:** Heatmap-Diff >= +0 PASS (keine Regression).
- **Gesamtziel ueber alle 5 Sub-Klassifizierer:** Heatmap 15/2 oder besser
  (heute 12/5).
- **Sekundaer:** Klassifizierer-Spalte in `train_dspy.py --stats` aufgeteilt
  und jede Sub-Spalte hat >= 10 Pairs (Mindest-Bootstrap-Mass).

## Offene Punkte

- Ob es einen `Combo-Klassifizierer` braucht wenn eine Phrase
  mehrere Typen kombiniert ("Eckbohrungen mit Fase") — wahrscheinlich
  nein, weil aktions_splitter solche Faelle in zwei Phrasen aufteilt;
  empirisch verifizieren.
- Modell-Wahl pro Sub-Agent: heute alle `gemma4:26b`. Wenn z.B.
  `edge_feature_classifier` empirisch mit 9b ausreichend laeuft, koennte
  das Latenz sparen. Erst nach Stabilisierung pruefen.
