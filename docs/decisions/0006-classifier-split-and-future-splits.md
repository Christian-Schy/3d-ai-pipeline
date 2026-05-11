# ADR 0006 — Klassifizierer-Split + nachfolgende Sub-Agent-Splits

- **Datum:** 2026-05-11
- **Status:** active (Plan, noch nicht implementiert)
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

Heutige Heatmap (`data/sessions/heatmap_20260511_210435.md`) zeigt **4 von 5
verbleibenden Fails sind Klassifizierer-Themen**: B1 v2 (Wert-Swap),
B_kombo_additive_anchor (Anker ignoriert), M_kombo (achse-Schema fehlt),
T_kombo (kante/abstand Coin-Flip). E_kombo ist Inventar-segmentierung.

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
| `pocket_classifier` | `tasche` | `{seite, laenge, breite, tiefe, drehung, abstand_*, versatz_*, kante_*}` |
| `slot_classifier` | `nut` | `{seite, laenge, breite, tiefe, achse, abstand_*, versatz_*}` |
| `pattern_classifier` | `lochkreis`, `eckbohrungen`, `bohrungsreihe` | `{seite, durchmesser, tiefe, anzahl, teilkreis_durchmesser, abstand_*, ...}` |
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

1. In `data/dspy_training/agent_contracts.py` fuenf neue `AgentContract`-
   Eintraege (`hole_classifier` ... `edge_feature_classifier`), jeweils
   `active=False` im ersten Schritt.
2. Fuenf neue `_adapter_*_classifier`-Funktionen — projizieren aus den
   bestehenden Klassifizierer-Traces nur die Eintraege ihres Typs.
3. `klassifizierer_traces.py`: keine Aenderung. Filter passiert im Adapter.
4. `train_dspy.py --stats` zeigt fuenf neue Zeilen mit Pair-Counts pro Typ.

**Phase B — Sub-Agent-Implementierung**

5. Neuer Code-Pfad in `src/agents/classifier_sub_agents.py` (oder
   gleichwertig) der pro Sub-Agent einen call macht. Eigene Prompt-Datei
   pro Sub-Agent in `data/prompts/prompt_classifier_<typ>.py`.
6. Initial: Prompts sind enge Auszuege aus dem heutigen
   `prompt_aktions_klassifizierer.py` (nur Tasche-Regeln im Tasche-Prompt etc).

**Phase C — Dispatcher + Fallback in Runtime**

7. `aktions_klassifizierer_node` bekommt:
   - `detect_typ(phrase)` als deterministischen Pre-Step
   - Routing zu `<typ>_classifier`-Agent wenn typ erkannt UND Sub-Agent
     aktiviert (per Feature-Flag z.B. `cfg.classifiers.hole_enabled`)
   - Fallback auf bestehenden Klassifizierer sonst
8. Aktivierungen kommen einzeln, je Sub-Agent eine Heatmap-Iteration:
   `active=True` setzen, trainieren, Heatmap-Diff, adopt-oder-rollback.

**Phase D — Klein-Bestaetigungs-Zyklus pro Sub-Agent**

Pro Sub-Agent: Backup-Bak-File anlegen, trainieren, Heatmap 2x laufen
lassen (Noise-Check), Layer-Diff vergleichen, dann erst Feature-Flag auf
true setzen.

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
