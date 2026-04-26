# Plan fuer Sonnet: Trainings-Trace-Generierung

**Ziel:** ~150 Pipeline-Traces fuer Stufe 1 erzeugen, damit DSPy die 5 aktiven
Agents (inventar, position_extractor, position_normalizer, teil_definierer,
assembly) optimieren kann.

**Wichtig:** Du annotierst nicht nur den User-Text, sondern den **ganzen
Pipeline-Durchlauf** (alle Agent-Ground-Truths). So bleiben Traces robust
gegen spaetere Agent-Splits.

---

## 1. Kontext — was du lesen musst, bevor du anfaengst

1. **[example_matrix.md](example_matrix.md)** — Slot-Enumerationen, Kombi-Regeln,
   Sprachstile. Daraus kommen die Szenarien.
2. **[agent_contracts.py](agent_contracts.py)** — Welche Felder jeder Agent
   als Input/Output hat. Dein annotierter Trace muss diese Felder enthalten.
3. **[reference_traces.py](reference_traces.py)** — **3 Referenz-Beispiele**
   (P0, P2, P3). Kopier die Struktur exakt.
4. **[../../../CLAUDE.md](../../../CLAUDE.md)** — Projekt-Vision, Konventionen
   (oben = X*Y der Rohdimensionen, hochkant-Logik, Determinismus vor Prompts).

Plus: `user_orientation_mental_model.md` im Memory — "vorne" = Bildschirm-"unten".

---

## 2. Dein Output

**Du fuegst Traces an `reference_traces.py::TRACES` an** (oder erzeugst eine
neue Datei `sonnet_traces.py` mit derselben Struktur; beides ist ok).

Jeder Trace ist ein dict mit:
- `id` — einzigartig, sprechend (z.B. `"platte_4loch_eck_p2_umgangssprachlich"`)
- `specification` — der User-Text
- `metadata` — `{difficulty, category, sprachstil, matrix_cell}`
- `inventar` — Output des Inventar-Agents
- `position_extractor` — NUR wenn multi-part
- `position_normalizer` — NUR wenn multi-part, ein Eintrag pro kind-teil
- `teil_definitionen` — Output des TeilDefinierer-Agents (pro Teil)
- `blueprint` — finales semantisches Blueprint (gleicher Key auch fuer BA)
- `assertions` — erwartetes Volumen/BBox/Feature-Count (optional, aber gern)

**Validiere nach jedem Batch:**
```bash
.venv/bin/python data/dspy_training/reference_traces.py
```
Zeigt Fehler und Coverage-Report.

---

## 3. Priorisierung — womit anfangen

**Tier 1 (hohe Prioritaet, ~80 Traces):** Single-Part, 1 Feature
- Jede FORM × jede FACE × jede POSITION-Klasse (P0, P1, P2) mindestens 2x
- 3 Sprachstile pro Zelle abwechseln
- Beispiele: Wuerfel + Bohrung, Platte + Tasche, Zylinder-Stirn + Bohrung,
  Quader + Nut, jede der 6 Seiten

**Tier 2 (~40 Traces):** Single-Part, Multi-Feature
- Ein Teil, 3–6 Features hintereinander
- Beispiel in Matrix Sektion 4, Beispiel E
- Mix aus P0/P1/P2, mindestens einmal pro Teil ein Muster (4x4, Lochkreis)

**Tier 3 (~25 Traces):** Multi-Part
- 2 Teile mit P3-Platzierung (rechts/oben/vorne centered)
- 2 Teile mit P4-Ueberstand/buendig
- 2 Teile mit P5-Anker (obere Ecke auf Kante, 10mm Versatz)
- 2 Teile mit P5 + Winkel (zusaetzlich Rotation)
- Einzelne 3-Teil-Assemblies (Kette: A → B an A → C an B)

**Tier 4 (~10 Traces, langsam):** Negativ- + Minimal-Paare
- Mehrdeutige Texte — Trace zeigt **wie die Pipeline idealerweise reagiert**
  (Rueckfrage oder Default-Annahme; bei Default den begruendeten Default wählen)
- Minimal-Paare aus Matrix Sektion 6 (gleich/unterschiedlich)

**NICHT machen in Stufe 1:**
- P7 (Zylinder-Mantel) — Resolver/Assembler kann das noch nicht
- Konturen / Freiform (Stufe 2)
- Modifications (spaeterer Tier)

---

## 4. Wie du einen Trace erzeugst (Arbeitsschritt)

**Schritt 1 — Szenario waehlen**
Nimm eine Matrix-Zelle, die noch unterbesetzt ist (siehe Coverage-Report).

**Schritt 2 — User-Text schreiben**
Waehle einen der 3 Sprachstile (knapp/technisch-ausfuehrlich/umgangssprachlich).
Achte auf die Konventionen im CLAUDE.md (oben = X*Y, hochkant-Logik).

**Schritt 3 — Inventar ausfuellen**
- Zaehle die Teile
- Liste sie mit `id`, `type`, `beschreibung`, `raw_params`
- Sammle die Aktionen (pro Feature ein Eintrag mit `teil_id`, `seite`, `beschreibung`)
- Achtung: `seite` ist die User-sprachliche Seite ("oben"/"rechts"/"vorne"),
  NICHT die Face-ID (">Z" etc.)

**Schritt 4 — PositionExtractor (nur multi-part)**
Pro kind-teil (d.h. ALLE ausser dem ersten aus `inventar.teile`):
- `teil_id`, `parent_hint`, `beschreibung`
- `beschreibung` ist ein **pre-digester Satz** zur Platzierung — Rauschen raus,
  nur was der Normalizer braucht (Seite + Kontaktflaeche + Versatz/Winkel).
- Root-Teil NIE eintragen.

**Schritt 5 — PositionNormalizer (nur multi-part)**
Pro kind-teil ein Eintrag:
```python
{"teil_id": "...",
 "input_sentence": "<was der Extractor produziert hat>",
 "output": _norm(parent=..., seite=..., ausrichtung=..., ...)}
```
Felder im `_norm(...)`:
- `parent` — das teil_id, an dem das Kind sitzt
- `seite` — aus Sicht des **Parents** (oben/unten/rechts/links/vorne/hinten)
- `ausrichtung` — `"centered"` / `"flush_right"` / `"flush_top"` / etc.
- `orientierung` — `"standard"` / `"hochkant"` / `"liegend"`
- `anliegende_flaeche` — welche Face des Kindes den Parent beruehrt (z.B. `"40x20"`)
- `abstand` — Edge-Distances, falls nicht centered
- `winkel` — 0 oder z.B. `45` (CCW als Konvention)
- `anker` — nur bei P5-Faellen, dict mit `kind_punkt`, `eltern_punkt`, `eltern_abstand`
- `pre_rotation` — falls vor dem Anchoring rotiert werden muss

**Schritt 6 — TeilDefinitionen**
Pro Teil ein Eintrag mit allen Features des Teils.
- `params` nach Orientation-Swap (bei `"hochkant"` sind Dimensionen getauscht —
  siehe blueprint_resolver.py, aber fuer semantisches Blueprint reicht es,
  hier die Roh-Params zu nehmen, der Resolver macht den Rest).
- Jedes Feature hat `id`, `type`, `params`, `position` (Semantic), `operation`.
- Feature-Position nutzt `_pos(side, alignment, edge_distances, angle_deg, notes)`.

**Schritt 7 — Blueprint (fuer assembly + BA)**
Flaches Dict aller Features mit Parent-Beziehungen.
- `build_order` — Reihenfolge: Root zuerst, dann Features des Roots,
  dann kind-teile, dann deren Features.
- `features` — Dict `feature_id → {type, params, parent, operation, position, orientation, notes}`
- Root-Teil hat `parent: None`.
- Fuer kind-teile ist `parent` = parent-teil-id, und die Position ist die
  Teil-Platzierung (gleicher Stil wie Feature-Position).

**Schritt 8 — Assertions (optional aber wertvoll)**
- `expected_bbox`: die Bounding-Box des fertigen Teils `[x, y, z]`
- `expected_volume_approx`: Summe aller adds minus subtracts (Naeherung, Zylinder mit π*r²*h)
- `expected_feature_count`: Dict `type → n`

**Schritt 9 — Validieren**
```bash
.venv/bin/python data/dspy_training/reference_traces.py
```
Schluckt nur wenn ALLE strukturell sauber sind.

---

## 5. Wann du Opus (mich) einbeziehen sollst

Sonnet kann 90% allein. Melde zurueck wenn:

1. **Resolver/Assembler-Gap** — du willst eine Beschreibung testen, aber bist
   dir nicht sicher ob die Pipeline das aktuell unterstuetzt (z.B. Zylinder-Mantel,
   Freiform, komplexe anker-Kombinationen). Ich schaue in den Code und entscheide:
   "geht heute" vs. "in Stufe 2 schieben".

2. **Anker-Semantik mehrdeutig** — beim P5-Trace bist du unsicher, ob `kind_punkt`
   = "obere linke Ecke" richtig serialisiert ist oder welche Konvention der
   Resolver erwartet. Zeig mir den Trace, ich verifiziere gegen `blueprint_resolver._apply_anchor`.

3. **Naming-Konflikte** — mehrere Features haben ploetzlich denselben Kandidaten-
   Namen ("bohrung_oben" 3x) und du bist unsicher, ob das Assembly-Probleme macht.

4. **Coverage-Luecken nach Batch** — wenn du ~50 Traces fertig hast, zeig mir den
   Coverage-Report (`coverage_report(TRACES)`). Ich identifiziere was fehlt und
   priorisier den naechsten Batch.

5. **Neuer Feature-Typ noetig** — du willst was trainieren, das im aktuellen
   Schema keinen Feature-Typ hat (z.B. Gewinde, Senkung mit Spezifikation).
   Schema erweitern = meine Entscheidung wegen Schema-Stabilitaet.

6. **DSPy-Training laeuft nicht** — nach dem ersten Training sehen wir uns
   gemeinsam die Dev-Scores an und entscheiden, ob ein Agent mehr/andere Traces
   braucht.

**Nicht fuer mich:** Text-Formulierung, Sprachstil-Variation, einfache P0/P1/P2
Traces, Assertions ausrechnen — das kannst du alles selbst.

---

## 6. Qualitaets-Checkliste pro Trace

Bevor du einen Trace commitest:

- [ ] `id` eindeutig und sprechend
- [ ] `metadata.difficulty` passt zur tatsaechlichen POSITION-Klasse
- [ ] `inventar.teil_count` == `len(inventar.teile)`
- [ ] `inventar.aktionen[*].teil_id` existiert in `inventar.teile`
- [ ] Bei multi-part: `position_extractor` fuer alle kind-teile, NICHT fuer root
- [ ] Bei multi-part: `position_normalizer` fuer alle kind-teile (gleiche IDs)
- [ ] `teil_definitionen[*].id` == `inventar.teile[*].id` (Set-Gleichheit)
- [ ] `blueprint.features` enthaelt alle teile UND alle features
- [ ] `blueprint.build_order` stimmt mit `features`-Keys ueberein
- [ ] `validate_all([trace])` gibt keine Fehler
- [ ] `specification` ist ein vernuenftiger deutscher Satz (kein broken Deutsch)
- [ ] Kein Inhaltsdoppel: gleiche Kombi noch nicht im Set

---

## 7. Ziel-Zahlen fuer Phase-1-Freigabe

| Tier | Ziel | Beispiele pro Zelle |
|------|------|---------------------|
| T1 Single-Part 1F | 80 | 3× pro (FORM × FACE × POSITION-Klasse) |
| T2 Single-Part NF | 40 | 3–6 Features, Mix P0/P1/P2 |
| T3 Multi-Part    | 25 | je 5 Traces pro P3/P4/P5/P5+Winkel/Kette |
| T4 Negativ/Paar  | 10 | siehe Matrix Sektion 5+6 |
| **Gesamt**       | **~155** | |

**Check:** `coverage_report(TRACES)` sollte am Ende jede POSITION-Klasse (P0–P6)
≥ 10x, jeden F-TYP ≥ 5x, jeden Sprachstil ≥ 40x abdecken.

---

## 8. Nach der Generierung (Opus-Part)

Wenn Sonnet ~50 Traces hat, macht Opus:

1. `train_dspy.py` erweitern um PositionExtractor + PositionNormalizer Agents
   (Signatures, Modules, Metriken). Heute nur fuer die 4 alten Agents.
2. Erster Trainings-Lauf auf lokalem Modell
3. Dev-Score-Review, Anpassungen
4. Golden-Tests in `tests/golden/` aus komplexen Traces erzeugen
5. Nach Vollzahl (~155 Traces): finales Training, Phase-1-Freigabe

---

## 9. Noch offen / Opus-TODOs vor Training-Start

- [ ] `train_dspy.py` um `position_extractor` und `position_normalizer` erweitern
  (neue Signatures, Metriken, Eintraege in AGENT_CONFIG) — **macht Opus nach
  Sonnets ersten 20-30 Traces, damit Struktur validiert ist.**
- [ ] Memory `project_position_vocabulary_gaps.md` als veraltet markieren
  (vorne/hinten ist inzwischen im Resolver).
- [ ] Pruefen ob `hole_pattern` in assembler.py sauber implementiert ist
  (Trace B nutzt es — falls noch nicht komplett, anpassen oder durch
  4× `hole_single` ersetzen).
