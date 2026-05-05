# ADR 0003 — Inventar + feature_definierer auf Pro-Aktion-Mikro-Calls

- **Datum:** 2026-05-05
- **Status:** proposed
- **Implementierung:** noch ausstehend

## Kontext

Die Pipeline hat heute zwei monolithische LLM-Stages, die mit
wachsender Spec-Groesse drastisch langsamer werden und bei
Verschachtelungen Information verlieren.

### Stage 1 — Inventar

Der `InventarAgent` ist heute zwei-stufig (`_extract_sequential` in
`src/agents/inventar_agent.py:176`):

- **Step A:** Teile-Liste extrahieren (1 LLM-Call, schnell, robust)
- **Step B:** pro Teil **eine Liste aller Aktionen** in einem
  einzigen LLM-Call

Step B bekommt also bei einem Wuerfel mit 6, 16 oder 50 Aktionen
einen einzigen riesigen Call. Das skaliert nicht und produziert in der
Praxis zwei Fehlerklassen:

1. **Verschachtelung wird verklumpt:** "Tasche 60x40x10 in der Tasche
   eine Bohrung 8mm tief" wird oft als 1 Aktion ausgegeben statt als
   2 (Tasche + Bohrung). Beobachtet in Run 6efaa489 (3 statt 6
   Aktionen) und Run 14fa8d40 (16 statt 24 Aktionen — 8 Bohrungen
   verschwunden).
2. **Sehr lange Latenz:** Step B kostet 17s, 50s, 67s, 148s in
   beobachteten Runs.

### Stage 2 — feature_definierer

`feature_definierer` wird heute **pro Teil** aufgerufen, mit der
**kompletten Aktionsliste** im Input. Bei 16 Aktionen auf einem Teil
wird das ein einziger LLM-Call, der alle 16 Aktionen zu Features
strukturiert. Beobachtete Latenzen: 70s, 165s, 200s, 313s.

Das ist der staerkste Bottleneck der Pipeline — in Run 14fa8d40
sogar 313s auf einen einzigen Call. Wenn die spaeter geplanten Cases
(mehrere Extrusionen mit jeweils mehreren Taschen + Bohrungen) hinzu
kommen, ist das nicht haltbar.

### Warum die heutige Architektur an die Grenze kommt

Beide Stages haben **eine gemeinsame Schwachstelle**: ein einzelner
LLM-Call traegt zuviel Verantwortung. Das fuehrt zu drei konkreten
Problemen:

1. **Skalierung:** Latenz waechst nicht-linear mit Spec-Komplexitaet.
2. **Genauigkeit:** Bei vielen Aktionen wird Information uebersehen
   oder verklumpt (siehe Verschachtelungs-Bug).
3. **Modifikations-Robustheit:** spaeter sollen User Teile/Aktionen
   modifizieren ("entferne die obere Bohrung", "verschiebe Tasche 3").
   Wenn Aktionen nur als Klumpen existieren, ist gezielte Re-
   Identifikation schwer.

## Entscheidung

**Alle drei Mega-LLM-Calls werden in Pro-Aktion-Mikro-Calls
aufgeloest.** Inventar Step B und feature_definierer werden so
umstrukturiert, dass jede Aktion **einen eigenen, kleinen, fokussierten
Call** bekommt. Aggregation passiert deterministisch im Code.

Das ist eine konsequente Anwendung der Projekt-Regel "Aufgaben so klein
und simpel wie moeglich".

### Neue Pipeline-Struktur (Stages 1 + 2)

```
heute:
  Inventar Step A  (1 Call)
  Inventar Step B  (1 Call/Teil mit ALLEN Aktionen)
  feature_definierer  (1 Call/Teil mit ALLEN Aktionen)

neu:
  Inventar Step A    (1 Call)               — Teile-Liste, wie heute
  Aktions-Splitter   (deterministisch)      — User-Spec -> Aktions-Phrasen
  Aktions-Klassifizierer (1 Call/Phrase)    — Phrase -> {typ, seite, parent}
  feature_definierer (1 Call/Aktion)        — Aktion -> 1 Feature
  Aggregator         (deterministisch)      — Features pro Teil zusammensetzen
```

### Komponenten-Definition

#### A) Aktions-Splitter (NEU, deterministisch)

**Eingabe:** User-Spec (string), Liste der Teile aus Step A.

**Aufgabe:** Spec in Aktions-Phrasen segmentieren. Eine Phrase ist die
zusammenhaengende Beschreibung **einer** Aktion (Tasche, Bohrung, Nut,
Fase, Rundung).

**Mechanismus:** rein regelbasiert. Splittet primaer an Komma + Seiten-
Schluesselwoertern (`oben`, `rechts`, `links`, `unten`, `vorne`,
`hinten`) und an Verschachtelungs-Markern (`in der tasche`,
`in der ausnehmung`, `darin`, `innerhalb`).

**Ausgabe:**

```json
[
  {"phrase": "rechts eine Tasche 60x40x10 ...", "teil_id": "wuerfel",
   "phrase_idx": 0, "parent_phrase_idx": null},
  {"phrase": "in der Tasche 15mm rechts eine Bohrung 8mm tief",
   "teil_id": "wuerfel", "phrase_idx": 1, "parent_phrase_idx": 0}
]
```

`parent_phrase_idx` ist gesetzt, wenn die Phrase eine Verschachtelung
ankuendigt ("in der Tasche..."). Der Splitter setzt sie auf den
unmittelbar vorhergehenden Eintrag des gleichen Teils — das ist die
einfachste Heuristik, die genau die Tasche-Bohrung-Konstellation
abdeckt.

**Warum deterministisch:** das ist Text-Strukturieren entlang klarer
Marker — keine Interpretation, also keine LLM-Aufgabe.

#### B) Aktions-Klassifizierer (NEU, LLM, klein)

**Eingabe:** eine einzelne Aktions-Phrase, Teil-Beschreibung,
optional die parent-Phrase.

**Aufgabe:** Phrase klassifizieren in einen strukturierten Eintrag.

**Ausgabe:**

```json
{
  "typ": "bohrung",
  "seite": "rechts",
  "beschreibung": "<original phrase>",
  "parent_aktion_idx": 0,
  "parameter_hints": {"durchmesser": 8, "tiefe": 10}
}
```

**Modell:** `gemma4:26b` (oder kleineres) mit `think=false`. Aufgabe
ist trivial — Klassifizieren in 5-6 Typen + Seite extrahieren.

**Warum LLM:** Textverstaendnis ("ist das eine Bohrung oder eine
Nut?") — genau die Domain die LLMs gut machen.

#### C) feature_definierer (REFACTOR, LLM, pro Aktion)

**Eingabe heute:** Teil + komplette Aktionsliste -> liefert
`teil_definition.features[]` mit allen Features.

**Eingabe neu:** Teil + **eine** Aktion (klassifiziert) -> liefert
**ein** Feature.

**Modell:** `gemma4:26b`. Aufgabe ist viel kleiner als heute, weil
nur 1 Aktion pro Call. Vermutlich `think=true` weiterhin sinnvoll.

**Warum kein neuer Agent, sondern Refactor:** der Agent existiert,
sein Schema-Output (`SemanticFeature`) bleibt unveraendert — nur
sein Eingabe-Schema wird schmaler.

#### D) Aggregator (NEU, deterministisch)

**Eingabe:** Liste aller einzeln-erzeugten Features +
Aktionen-Klassifikationen.

**Aufgabe:** baut die finale `teil_definitionen[]`-Struktur. Setzt
Reihenfolge, weist `parent`-Felder gemaess `parent_aktion_idx` auf
die korrekte Pocket-Feature-ID.

**Warum deterministisch:** das ist reines Zusammenfuegen — Listen
bauen, Indizes uebersetzen.

## Verworfene Alternativen

### Weg 1 — kleiner Verschachtelungs-Splitter zwischen Inventar und feature_definierer

Ein zusaetzlicher Mini-Agent, der nur Aktionen mit "in der tasche"-
Hinweis in 2 Aktionen aufsplittet. Inventar bleibt unangetastet.

**Verworfen weil:**
- Loest nur Bug A (Verschachtelung), nicht den Latenz-Bottleneck.
- Mega-Calls in Step B und feature_definierer bleiben.
- Skaliert nicht mit zukuenftigen Anforderungen (mehrere Extrusionen
  mit vielen Taschen+Bohrungen).
- Wegwerf-Code: muss in Phase 2 sowieso wieder raus, wenn ohnehin
  pro-Aktion-Calls kommen.

### Weg 2 — Prompt-Erweiterung im AKTIONEN_SYSTEM (Inventar Step B)

Im Prompt eine Regel "Verschachtelung -> 2 Aktionen" + Few-Shot
einfuegen.

**Verworfen weil:**
- Step B wird ueberladen (verstoesst gegen "kein Agent ueberladen").
- DSPy-Demos fuer Step B muessten parallel ergaenzt werden, sonst
  sendet der Trainings-Pfad ein Konfliktsignal an das Modell.
- Mega-Call bleibt -> Latenz nicht behoben.
- Skaliert nicht mit Spec-Groesse.

### Weg 4 — Mehr Modell-Power statt Splitting

Inventar/feature_definierer auf groesseres Modell heben (z.B. 30b
oder cloud LLM), `think=true` aktiviert lassen.

**Verworfen weil:**
- Empirisch geprueft — `gemma4:26b` mit `think=true` schafft
  Verschachtelung bisher nicht.
- Das Latenz-Problem wird mit groesseren Modellen schlimmer, nicht
  besser.
- Lokal-Modell-Ziel (siehe CLAUDE.md "System soll mit kleinen
  lokalen Modellen funktionieren") wird nicht erfuellt.

## Konsequenzen

### Positiv

- **Skalierung:** Latenz waechst linear mit Spec-Komplexitaet, nicht
  mehr exponentiell. 24 Aktionen = 24 kleine Calls (parallelisierbar)
  statt 1 Mega-Call.
- **Genauigkeit:** jede Aktion bekommt einen fokussierten Call, kein
  Verklumpen mehr.
- **Verschachtelung:** wird vom deterministischen Splitter erkannt,
  nicht mehr vom LLM.
- **Modifikations-Robustheit:** jede Aktion hat eine eigene stabile
  ID (`teil_id` + `phrase_idx`). Spaetere Modifikations-Pfade koennen
  gezielt referenzieren.
- **Parallelisierung moeglich:** Pro-Aktions-Calls sind unabhaengig
  und koennten parallel gefeuert werden (nicht in dieser ADR
  implementiert, aber Architektur ermoeglicht es).
- **Bug A (Verschachtelung) automatisch geloest** ohne separaten Patch.

### Negativ / zu beachten

- **DSPy-Optimierungen invalidiert:** `inventar_optimized.json` und
  `feature_definierer_optimized.json` in `data/dspy_optimized/` sind
  fuer das alte Schema trainiert. Nach diesem Umbau: Re-Training
  noetig. Das ist laut Memory `project_phase_1_abschluss.md` ohnehin
  geplant — Phase 1 muss erst stabil sein, dann DSPy-Re-Training.
- **Mehr LLM-Roundtrips:** statt 1 Call pro Stage jetzt N Calls.
  Bei kleinen Specs (3-5 Aktionen) ist das pro-Roundtrip-Overhead
  fuehlbar. Akzeptabel weil die problematischen Faelle (langes Spec
  mit vielen Aktionen) drastisch profitieren.
- **agent_contracts.py erweitern:** zwei neue Adapter (Aktions-
  Klassifizierer, Pro-Aktion-feature_definierer). Bestehende
  Adapter wo unveraendert bleiben.
- **Pipeline-Routing umbauen:** in `src/graph/pipeline.py` werden
  zwei neue Nodes verdrahtet, ein bestehender (feature_definierer)
  verschiebt sich in der Topologie.
- **Aggregator-Schicht ist neu:** muss sauber getestet sein, weil
  ein Bug hier alle Features falsch zuordnet.

### Risiken

- **Splitter-Heuristik unscharf:** wenn ein User-Spec ungewoehnliche
  Strukturen hat, splittet der Splitter falsch (zu viele oder zu
  wenige Phrasen). Mitigation: Splitter-Regeln per Test gegen
  vorhandene Trainings-Specs absichern.
- **parent_aktion_idx fehlerhaft:** Verschachtelung wird ueber den
  unmittelbar vorhergehenden Eintrag verbunden. Wenn der User schreibt
  "Tasche A, Tasche B, in der ersten Tasche eine Bohrung" — das
  bricht die Heuristik. Mitigation: Klassifizierer kann optional
  parent_aktion_idx korrigieren.

## Implementierungs-Stufen

Die Umsetzung erfolgt in nachpruefbaren Stufen. Jede Stufe ist fuer
sich testbar und kann in einem separaten Commit landen.

### Stufe 1 — Aktions-Splitter (deterministisch)

- **Code:** neuer Modul `src/tools/aktions_splitter.py`
- **Aufgabe:** Spec + Teile-Liste -> Liste von Phrasen mit
  parent_phrase_idx.
- **Tests:** `tests/tools/test_aktions_splitter.py`
  - Beispiel-Specs aus Run 965da548, 6efaa489, 14fa8d40
  - Edge-Cases: Phrasen mit/ohne Komma, Verschachtelung 1-tief,
    mehrere Teile
- **Pipeline-Integration:** noch nicht — zuerst standalone testbar.

### Stufe 2 — Aktions-Klassifizierer-Agent

- **Code:** neuer Agent `src/agents/aktions_klassifizierer.py`
- **Prompt:** neuer Prompt `data/prompts/prompt_aktions_klassifizierer.py`
  — minimaler Output-Schema, 4-5 Few-Shot-Beispiele
- **DSPy-Hooks:** `dspy_demo_fields` definieren, agent_contracts.py
  Adapter ergaenzen, aber **kein Training** in dieser Stufe
- **Tests:** `tests/agents/test_aktions_klassifizierer.py`
  - Mock LLM, prueft Schema-Validierung, parent-handling

### Stufe 3 — feature_definierer-Refactor (Pro-Aktion)

- **Code:** `src/agents/feature_definierer.py` umbauen
- **Eingabe-Schema aendern:** statt Teil+Aktionsliste -> Teil+1 Aktion
- **Output-Schema unveraendert:** liefert weiterhin ein
  `SemanticFeature`-Objekt
- **Prompt-Anpassung:** Few-Shots auf 1-Aktion-pro-Call umbauen
- **DSPy-Hooks:** vorhandene `dspy_demo_fields` aktualisieren
- **Tests:** bestehende `tests/agents/test_feature_definierer*.py`
  durchgehen, Schema-Aenderung berucksichtigen

### Stufe 4 — Aggregator

- **Code:** neuer Modul `src/tools/aktions_aggregator.py`
- **Aufgabe:** Pro-Aktion-Features + Klassifikationen ->
  finale `teil_definitionen[]`-Struktur
- **parent-Aufloesung:** `parent_aktion_idx` -> Pocket-Feature-ID
- **Tests:** `tests/tools/test_aktions_aggregator.py`

### Stufe 5 — Pipeline-Verdrahtung

- **Code:** `src/graph/pipeline.py`, `src/graph/nodes/planning_nodes.py`
- **Neue Nodes:** `aktions_splitter_node`, `aktions_klassifizierer_node`
- **Modifizierter Node:** `feature_definierer_node` ruft neuen Pro-
  Aktion-Pfad auf
- **Neuer Node:** `aktions_aggregator_node` direkt nach feature_definierer
- **Routing:** unveraendert bzgl. coordinate_validator/plan_validator
- **Tests:** `tests/graph/` falls vorhanden, sonst End-to-End-Smoke
  ueber bekannte Test-Specs

### Stufe 6 — Real-Run-Verifikation

- **Specs:** mindestens 3 Real-Runs aus runs.jsonl, davon
  - 1× klein (Run 70d27d2f, 5-6 Aktionen)
  - 1× mittel (Run 6efaa489, 3 Pockets mit Bohrung)
  - 1× gross (Run 14fa8d40, 16 Aktionen mit Verschachtelung)
- **Erfolgsmetrik:**
  - Verschachtelte Bohrungen kommen alle als Features durch
  - feature_definierer-Latenz pro Call < 30s (vorher bis 313s)
  - Keine zweite-Iteration durch coordinate_validator-False-Positives

### Stufe 7 — DSPy-Re-Training (separater Commit, separate ADR)

Erst nach Stabilisierung der Stufen 1-6.

- Trainings-Demos fuer Aktions-Klassifizierer (neu)
- Trainings-Demos fuer feature_definierer im neuen Schema
- Trainings-Demos fuer Inventar Step A (unveraendert, kann
  uebernommen werden)
- Inventar Step B faellt komplett weg

## Schnittstellen-Vertrag

Damit der Umbau nicht Schema-Drift verursacht, hier die
einzuhaltenden Vertraege:

### Aktions-Splitter -> Aktions-Klassifizierer

```json
{
  "phrase": str,                    // Original-Substring der Spec
  "teil_id": str,                   // Eindeutige Teil-ID aus Step A
  "phrase_idx": int,                // 0-basiert, fortlaufend pro Teil
  "parent_phrase_idx": int | null   // Vorheriger Eintrag bei
                                    // Verschachtelung, sonst null
}
```

### Aktions-Klassifizierer -> feature_definierer

```json
{
  "typ": "tasche|bohrung|nut|fase|rundung",
  "seite": "oben|unten|rechts|links|vorne|hinten",
  "beschreibung": str,              // unveraenderte Original-Phrase
  "teil_id": str,
  "phrase_idx": int,
  "parent_phrase_idx": int | null,
  "parameter_hints": {              // optional, was der Klassifizierer
                                    // schon parsen konnte
    "durchmesser": float,
    "tiefe": float,
    ...
  }
}
```

### feature_definierer -> Aggregator

```json
// Genau ein SemanticFeature-Objekt, wie heute, plus Marker
{
  "id": str,
  "type": str,
  "params": {...},
  "position": {...},
  "parent": str | null,
  "operation": "add|subtract",
  "_phrase_idx": int,               // Marker fuer Aggregator
  "_parent_phrase_idx": int | null  // Marker fuer Aggregator
}
```

Aggregator entfernt die `_phrase_idx`-Marker und uebersetzt
`_parent_phrase_idx` in die richtige Feature-ID. Output ist eine
saubere `teil_definition`, schema-kompatibel zu heute.

## Auswirkungen auf andere Komponenten

- **`pocket_child_placer`:** koennte schmaler werden oder ganz
  entfallen. Wenn der Aktions-Splitter Verschachtelung schon erkennt
  und `parent_phrase_idx` setzt, ist die Pocket-Bohrung-Zuordnung
  bereits vor feature_definierer geklaert. **Zunaechst** bleibt
  pocket_child_placer drin als Sicherheitsnetz, wird in einer
  spaeteren ADR ggf. abgeschafft.
- **`platzierer`:** unveraendert. Single-Part-Shortcut bleibt.
- **`text_splitter` und `position_extractor`:** unveraendert in der
  Funktion, aber moeglicherweise in der Reihenfolge angepasst.
- **`coordinate_validator` und `plan_validator`:** unveraendert.
- **`blueprint_resolver`:** unveraendert. Der Aggregator liefert
  ein zum heutigen Schema kompatibles Blueprint.

## Definition of Done

- [ ] Stufe 1-6 implementiert mit Tests gruen
- [ ] CHANGELOG.md-Eintrag pro Stufe-Commit
- [ ] CLAUDE.md aktualisiert: Pipeline-Flow zeigt neue Stages
- [ ] `feedback_richer_schema_not_rules.md`-Memory ggf. aktualisiert
- [ ] Real-Run-Verifikation auf den 3 Test-Specs erfolgreich
- [ ] DSPy-Status dokumentiert (welche Demos invalidiert, welche neu
      gebraucht werden — fuer Stufe 7)
