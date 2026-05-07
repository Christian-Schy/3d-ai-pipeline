# ADR 0004 — Bug 7 + Bug 8 aus Real-Run-Analyse: Anchor-Edge-Endpunkte + Splitter-Eingang

- **Datum:** 2026-05-07
- **Status:** proposed (Plan fuer naechste Iteration)
- **Implementierung:** offen

Begleitdokument: die ersten vier Bugs (1, 2, 5, 6) aus derselben
Analyse sind in Commit `980a0ac` gefixt. Bug 3 + 4 in einem direkten
Folge-Commit. Bug 7 + 8 brauchen mehr Vorlauf — daher dieser ADR.

Quell-Runs: `e3ddd2d0`, `da35a6ce`, `e1def0fa`. Vollstaendige Bug-
Tabelle siehe CHANGELOG-Eintrag vom 2026-05-07.

---

## Bug 7 — Anchor-Edge-Endpunkte fehlen im Vokabular

### Symptom

User-Phrase fuer Plattenplatzierung:

```
vorne soll eine platte hin mit 140x20x40, die 140x20 seite liegt
auf, die rechte untere ecke auf der rechten kante um 10mm nach
oben versetzt und um 20 grad gegen uhrzeigersinn gedreht
```

Erwartung: Plattes bottom-right Ecke beruehrt die rechte Kante des
<Y-Face am UNTEREN Ende der Kante, plus 10mm hoch (also Z ≈ -90).

Tatsaechlich (Run da35a6ce / e1def0fa): Platte center bei
`(30.80, -4.54)` auf `<Y` — die Plate sitzt mittig statt am Boden.
Der Resolver mappt `parent_point="right_edge"` auf den **Mittelpunkt**
der rechten Kante (Z=0), ignoriert dass "untere ecke" semantisch das
**untere Ende** der Eltern-Kante anpeilt.

### Wurzel

In `src/tools/blueprint_resolver.py:_ANCHOR_POINT_LUT` (~Z. 624):

```python
_ANCHOR_POINT_LUT = {
    "center":     (0.0,  0.0),
    "top_left":   (-0.5, +0.5),
    ...
    # "right_edge", "left_edge", "top_edge", "bottom_edge" werden
    # vom Aufrufer auf den jeweiligen Edge-Mittelpunkt gemappt.
}
```

Plus die User-Konvention aus Memory `feedback_anchor_semantics.md`:
"Default-Punkte: Flaeche/Kante = Mittelpunkt, Ecke = Punkt. Resolver
bleibt regel-arm."

Diese Konvention ist gut — aber sie deckt den Fall "Ecke an Kante"
nicht ab. Der User nennt eine Kante UND eine Ecke (am Eltern-Teil)
und meint damit den Endpunkt der Kante, an dem genau diese Ecke
liegt.

### Loesung — Vokabular-Erweiterung, Resolver bleibt regel-arm

Anchor-LUT additiv um Endpunkt-Schluessel erweitern:

```
right_edge_top, right_edge_bottom
left_edge_top,  left_edge_bottom
top_edge_left,  top_edge_right
bottom_edge_left, bottom_edge_right
```

Plus Aliase in deutscher Notation, weil der Platzierer-Prompt sie
womoeglich so ausgibt:

```
rechte_kante_unten, rechte_kante_oben, ...
```

Werte: 2D-Koordinaten in Face-Frame (-0.5 … +0.5):

```
right_edge_bottom  = (+0.5, -0.5)   # = bottom_right
right_edge_top     = (+0.5, +0.5)   # = top_right
...
```

Das duplizieren ist OK — es macht den Platzierer-Output explizit
("die rechte Kante am unteren Ende") ohne den Resolver mit Heuristik
zu belasten.

### Was sich aendert

**Resolver** (`src/tools/blueprint_resolver.py`):

- `_ANCHOR_POINT_LUT` um die acht Endpunkt-Eintraege ergaenzen, plus
  deutsche Aliase (`rechte_kante_unten` etc.).
- Tests in `tests/tools/test_anchor_placement.py` plus die existierende
  `test_position_builder_anchor.py` um Endpunkt-Faelle erweitern.

**Platzierer-Prompt** (`data/prompts/prompt_position_normalizer.py`
oder das aktive Position-Normalizer-Prompt):

- Neue Erkennungs-Regel: "wenn der User eine Pocket-Ecke und eine
  Cube-Kante zusammen nennt ('die rechte UNTERE Ecke auf der RECHTEN
  Kante'), nimm den passenden Endpunkt der Kante als parent_point
  statt der Mitte".
- Plus Few-Shot:
  ```
  "die rechte untere ecke auf der rechten kante 10mm nach oben"
  → child_point="bottom_right", parent_point="right_edge_bottom",
    offset={up: 10}
  ```

**Tests:**

- `tests/tools/test_anchor_placement.py`: Endpunkt-Resolution,
  besonders `right_edge_bottom + offset(up=10)` → erwartete `(ox, oy)`
  fuer ein 140x20x40-Plate auf einem 200x200x200-Wuerfel <Y-Face.
- `tests/agents/test_position_normalizer_*.py` (falls existent):
  Few-Shot-Cases fuer "Ecke + Kante"-Phrasing.

### Nicht-Ziele

- Kein Heuristik-Fallback im Resolver — bleibt regel-arm.
- Keine Aenderung am bestehenden `right_edge` (= Mittelpunkt). Nur
  additiv.
- Keine Aenderung am Platzierer-Output-Schema. Die neuen Werte
  passen schon ins bestehende `parent_point: str`-Feld.

### Schritte (Reihenfolge)

1. LUT erweitern + Tests fuer die neuen Schluessel (~30 Zeilen Code,
   ~6 Tests).
2. Smoke-Resolver-Test mit echtem `da35a6ce`-Spec → Plate-Position
   pruefen, gegen Erwartung `(ox≈30, oy≈-95)` validieren.
3. Platzierer-Prompt um Erkennungs-Regel + Few-Shot erweitern.
4. End-to-End-Run mit der `da35a6ce`-Spec lokal laufen lassen,
   pruefen dass die Plate jetzt bei der unteren Ecke der rechten
   Kante landet.

### Tradeoff / Alternative

Alternative: Anchor-Schema um ein zusaetzliches `parent_endpoint`-Feld
erweitern (`parent_point="right_edge", parent_endpoint="bottom"`).
Sauberer im Sinn von Trennung "wo liegt die Kante" / "an welcher
Stelle der Kante", aber bricht das aktuelle Schema. Endpunkt-
Schluessel im selben Feld sind additiv und reichen voellig — daher
gewaehlt.

---

## Bug 8 — Splitter teil_id-Zuweisung order-dependent

### Symptom

User-Spec (Run `e1def0fa`):

```
200mm würfel oben soll [cube tasche 1 + bohrungen],
oben soll [cube tasche 2 + bohrungen],
auf der rechten seite eine bohrung [...],     ← gemeint: Platte
auf der rechten seite eine nut [...],          ← gemeint: Platte
auf der rechten seite eine nut [...],          ← gemeint: Platte
auf der rechten seite noch eine bohrung [...], ← gemeint: Platte
vorne soll eine platte hin mit 140x20x40,      ← Platte erst HIER
die 140x20 seite liegt auf [...]
```

Der `aktions_splitter` weist die vier "auf der rechten seite ..."-
Phrasen `teil_id="wuerfel"` zu, weil:

1. Keine der Phrasen enthaelt "platte" als Substring.
2. Der Splitter kennt zum Zeitpunkt nur den Cube als
   `last_teil` (Platte-Decl kommt erst spaeter).

Folge: drei Plattefeatures landen auf dem Wuerfel ("oben waren mehr
aktionen als gewollt"), die Plattes rechte Seite bleibt leer ("rechts
haben die dafür gefehlt").

### Wurzel

`_assign_teil_id` in `src/tools/aktions_splitter.py:182-195` ist
**linear-skannend**: pro Comma-Segment Substring-Match auf die
Teil-IDs, sonst auf `last_teil` (das letzte Segment, das einen
Treffer hatte) zurueckfallen. Forward-Lookahead gibt es nicht.

Komplikation: die heutige Pipeline-Reihenfolge ist:

```
inventar
  → aktions_splitter           ← liest RAW spec
  → aktions_klassifizierer
  → text_splitter              ← teilt spec in per-teil chunks
  → position_extractor         ← labelt placement vs feature
  → feature_definierer
```

Der `aktions_splitter` laeuft VOR dem `text_splitter`/`position_extractor`,
obwohl die ja schon eine bessere Per-Teil-Zuordnung haben (siehe
`feature_sentences[teil_id]` in da35a6ce — labeler hat die Plattenfeatures
korrekt als `auf der platte ...` zugeordnet, nur leider nutzt der
Splitter das nicht).

### Loesungs-Optionen

#### Option A — Forward-Lookahead im Splitter (klein)

`_assign_teil_id` erweitern:

```python
def _assign_teil_ids_two_pass(segments, teil_ids):
    explicit = [_first_match(seg, teil_ids) for seg in segments]
    last = None
    next_anchor = None  # cached forward lookahead
    for i, seg in enumerate(segments):
        if explicit[i] is not None:
            last = explicit[i]
            yield last
        elif last is None:
            # noch kein anchor gesehen → nimm den naechsten
            next_anchor = next_anchor or _next_anchor(explicit, i)
            yield next_anchor or teil_ids[0]
        else:
            yield last
```

Tradeoff: **last_seen schlaegt forward-lookahead**. Heisst:
`e1def0fa` ist NICHT geheilt (segment 0 ist bereits anchor=wuerfel,
also bleibt last_teil=wuerfel fuer die Plattenfeatures). Hilft nur,
wenn die Plattefeatures GANZ AM ANFANG der Spec stehen.

Fazit: Option A ist eine Rumpf-Loesung und faehrt fuer den
Real-Run-Fall ins Leere.

#### Option B — Splitter aus position_extractor.feature_sentences speisen (gross)

Architektur-Refactor:

```
inventar
  → text_splitter              ← braucht NUR rohe spec + teile
  → position_extractor         ← labelt placement / feature pro teil
  → aktions_splitter           ← splittet feature_sentences[teil_id]
  → aktions_klassifizierer
  → feature_definierer
```

Konkret:

- `aktions_splitter` bekommt einen anderen Input — `feature_sentences`
  pro Teil statt rohe Spec.
- API-Change: `split_spec_into_aktionen(spec, teile)` wird zu
  `split_feature_sentences_per_teil(positionen)` (oder besser ein
  Wrapper, der pro Teil das alte split_spec_into_aktionen aufruft).
- Pipeline-Edges in `src/graph/pipeline.py:264-267`:
  ```
  inventar → text_splitter → position_extractor
           → aktions_splitter → aktions_klassifizierer
           → feature_definierer
  ```
- `text_splitter` und `position_extractor` muessen ohne `aktions_phrases`
  funktionieren (oder beide bekommen einen Default-Input). Ggf.
  `text_splitter` braucht andere Heuristik fuer Per-Teil-Chunks.

Konsequenzen / Risiken:

- `text_splitter` lief bisher AFTER `klassifizierer` (warum eigentlich?
  klaeren). Wenn er VOR Splitter laufen kann, dann ist die
  Reihenfolge kein Problem.
- `position_extractor` ist heute LLM-basiert. Wenn er fuer e1def0fa
  die Plattenfeatures auch nicht richtig zuordnet (siehe trace:
  feature_sentences=[] fuer Platte), dann hilft auch dieser Refactor
  nicht. **Erstmal pruefen ob der Labeler bei e1def0fa die Sentences
  bei besserer Per-Teil-Chunkung richtig labeln wuerde.**

#### Option C — `text_splitter` schlauer machen (mittel)

Wenn das Hauptproblem das Per-Teil-Chunking ist, koennte `text_splitter`
einen Two-Pass machen: erst alle Teile + ihre Decl-Positionen
identifizieren, dann Phrasen-Chunks per next-anchor zuordnen — auch
zurueckblickend wenn ein spaeterer Anchor "zieht" (z.B. wenn vor dem
naechsten Anchor mehrere Phrasen mit "auf der platte" kommen).

Tradeoff: braucht weiterhin LLM-Verstaendnis, aber Heuristik-Anteil
waechst. Risiko: ueberraschende Mis-Chunking-Faelle.

### Empfehlung

1. **Erst pruefen** (3-Step-Plan):
   - Pruefe `text_splitter`-Output fuer da35a6ce + e1def0fa: hat er
     die richtigen Per-Teil-Chunks? Falls ja → Option B funktioniert.
     Falls nein → Bug liegt eigentlich im text_splitter.
   - Pruefe `position_extractor`-Output mit korrekten Per-Teil-Chunks:
     wuerde der LLM-Labeler aus dem korrekten Platte-Chunk die richtigen
     feature_sentences emittieren?
2. **Refactor in der Reihenfolge**:
   - Erst Pipeline-Edges umstellen + API-Anpassung Splitter (Option B).
   - Dann ggf. text_splitter haerten (Option C).
3. **Nicht** Option A — produziert keine Ende-zu-Ende-Loesung fuer
   die realen User-Specs.

### Schritte (Option B)

1. Investigation: `text_splitter` und `position_extractor` Outputs aus
   den drei Real-Runs ansehen, dokumentieren, ob die Per-Teil-Chunks
   sauber sind.
2. Wenn ja: `aktions_splitter` API anpassen — neuer Eintrittspunkt
   `split_feature_sentences_per_teil(positionen, teile)` der pro Teil
   die existierende Logik aufruft.
3. Pipeline-Edges in `src/graph/pipeline.py` umstellen:
   `inventar → text_splitter → position_extractor → aktions_splitter
    → aktions_klassifizierer → feature_definierer`.
4. State-Felder: `aktions_phrases` bleibt (Output des splitter, jetzt
   pro-Teil-aware).
5. `aktions_splitter_node` umstellen: liest `position_extrakt` statt
   `specification`.
6. Tests:
   - Splitter-Unit-Tests: neuer Eintrittspunkt mit feature_sentences
     pro Teil → korrekte Phrasen + teil_id.
   - Pipeline-Integration: e1def0fa-Spec lokal laufen lassen, pruefen
     dass Plattefeatures auf der Platte landen.
7. Wenn `position_extractor` Per-Teil-Labeling nicht zuverlaessig
   schafft (e1def0fa-Plattafall): zusaetzlich Option C (text_splitter
   Two-Pass) angehen.

### Risiken

- `text_splitter` und `position_extractor` koennten heute Edge-Cases
  haben, die durch den Refactor freigelegt werden. Vor dem Edge-Umbau
  Pruefung.
- Bestehende Tests in `tests/tools/test_aktions_splitter.py` arbeiten
  alle mit `split_spec_into_aktionen(spec, teile)` direkt — die alte
  Funktion sollte erhalten bleiben, der neue Eintrittspunkt ist ein
  Adapter.
- Das `change_description`/Modify-Flow nutzt heute den blueprint_architect
  (alte Kette) — der Refactor darf den nicht beruehren.

---

## Reihenfolge im naechsten Chat

1. ADR lesen (diese Datei).
2. **Bug 7 zuerst** (Anchor-Endpunkte) — kleiner, isoliert,
   deterministisch testbar. Setzt LUT + Prompt-Few-Shot um, fertig.
3. **Bug 8 danach** — beginnt mit Investigation (Schritt 1 oben),
   dann Option B umsetzen.
4. Beide Bugs in separaten Commits + Changelog-Eintraegen.

## Referenz-Daten

Real-Runs zur Verifikation:
- `e3ddd2d0` — 16 Pocket-Setup, beweist Bug 1+2+3+4 (alle gefixt).
- `da35a6ce` — Platte mit 3 echten Features auf der Rechtsseite,
  Phantom-Features durch ignorieren-Filter (Bug 6 gefixt). Bug 7
  zeigt sich an Plattenposition `(30.80, -4.54)`.
- `e1def0fa` — gleiche Plattenspec, aber Features VOR Plattedekl,
  beweist Bug 8 (Splitter-Order).

Erwartete Outputs nach Bug 7-Fix:
- Plate-Position auf <Y-Face: `offset_x ≈ 30.80, offset_y ≈ -95.5`
  (mit child-corner-bottom_right an parent right_edge_bottom + 10mm
  hoch).

Erwartete Outputs nach Bug 8-Fix:
- Spec e1def0fa: Plattefeatures (1 Bohrung, 2 Nuten, 1 weitere
  Bohrung) erscheinen alle in `blueprint.features` mit
  `parent="platte"`, NICHT auf dem Wuerfel.
