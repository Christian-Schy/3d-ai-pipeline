# ADR 0005 — Regressions-Baseline + Feature-Matrix vor Architektur-Pivot

- **Datum:** 2026-05-08
- **Status:** active (Plan fuer naechste Wochen)
- **Vorgaenger-ADRs:** 0003 (Pro-Aktion-Mikro-Calls), 0004 (Bug 7+8)

## Problem

Wir patchen seit Tagen Bugs aus Real-Runs. Jeder Fix veraendert Verhalten
woanders, und wir sehen es erst wenn der naechste Real-Run schiefgeht.
Beispiel-Dynamik aus den letzten Tagen:

- Bug 7 fixt Anchor-Endpunkte → Bug C zerstoert Plate-Position
- Bug A fixt Phantom-Pockets → Bug D Default-Regel veraendert Feature-Zuweisung
- 9cfa059c: Feature-Zuweisung an extrudierte Platten "geht gar nicht mehr"
  (vermutlich Bug-D-Regression, unbestaetigt)

**Wurzel:** Wir testen unit-level (Splitter, Resolver, Assembler), aber
nicht **Pipeline-Outputs fuer realistische Spec-Mischungen**. Was bricht
ist immer der Aggregations-Pfad zwischen LLM-Calls und deterministischen
Tools.

## Entscheidung

**Bevor wir architektur-pivoten oder DSPy-trainieren, bauen wir eine
Regressions-Baseline.** Zwei Test-Layer:

Die Baseline ist nicht auf Demo-Teile beschraenkt. Sie soll komplexe
Standard-Feature-Kompositionen stabilisieren, aber gestuft:

| Level | Fokus | Gate-Status |
|-------|-------|-------------|
| 1 | Einzel-Features: Bohrung, Tasche, Nut, einfache Extrusion | hartes Gate |
| 2 | mehrere Features auf einem Grundkoerper | hartes Gate nach Level 1 |
| 3 | Nested Features wie Bohrung in Tasche | gezielt hart fuer NEST1 |
| 4 | Extrusionen mit Features | hart sobald E/EF-Basis gruen ist |
| 5 | grosse Kombi-Teile mit vielen Varianten | Stress-/Zielbild, nicht erstes hartes Gate |

Damit koennen wir schon frueh grosse Teile beobachten, ohne die Arbeit an
den kleineren, besser attribuierbaren Fehlern zu blockieren.

### Layer 1 — Component-Goldens (deterministisch, schnell)

Testen einzelne Pipeline-Stufen deterministisch:

```
tests/golden/components/<scope>/
  resolver/
    input_semantic.json     ← semantic blueprint
    expected_resolved.json  ← erwartetes resolved blueprint
  splitter/
    spec.txt                ← spec
    expected_phrases.json   ← erwartete aktions_splitter Phrasen
  assembler/
    input_resolved.json     ← resolved blueprint
    expected_code_snippet.txt ← erwartete cadquery Zeilen
```

Vorteil: laeuft in Millisekunden, kein LLM-Cost, Regressionen sofort
sichtbar. Faengt 80% der Bugs (alle die in deterministischen Tools sitzen).

### Layer 2 — Pipeline-Goldens (LLM, langsam, mit Text-Variation)

Existierende `tests/golden/<slug>/` Struktur erweitern:
- Pro Feature mehrere `spec.v1.txt`, `spec.v2.txt`, `spec.v3.txt`
  Variationen mit gleichem semantischen Inhalt aber verschiedenem Wording
- Ein gemeinsames `expected_blueprint.json` (Toleranzen wie heute)

Beispiel-Variation-Pattern:
```
B1 — Bohrung Versatz aus Mitte
  spec.v1.txt: "200mm wuerfel, oben eine 10mm bohrung 10mm nach rechts und 20mm nach oben versetzt 5mm tief"
  spec.v2.txt: "200mm wuerfel, oben eine 10mm bohrung um 10 nach rechts versetzt um 20 nach oben versetzt 5 tief"
  spec.v3.txt: "200mm wuerfel, oben 10mm nach rechts 20mm nach oben versetzt eine 10mm bohrung 5mm tief"
```

Alle drei muessen das **gleiche** Blueprint produzieren.

Vorteil: testet LLM-Sprachverstaendnis. **Layer-2-Goldens werden NICHT
auf jedem Commit gefahren** (zu teuer/langsam). Nur:
- Vor Releases / Architektur-Aenderungen
- Wenn Layer-1 alles gruen sagt aber Real-Run schief geht

## Feature-Matrix (Coverage-Plan)

Liste der Features die heute funktionieren sollen (User-Definition,
2026-05-08). Pro Eintrag mindestens **ein Layer-1-Component-Golden**
(deterministisch) und **ein Layer-2-Pipeline-Golden mit 2+ Variationen**.

### B — Wuerfel + Bohrungen

| ID | Variation | Beispiel-Spec |
|----|-----------|---------------|
| B1 | Versatz aus Mitte | `oben eine 10mm bohrung 10mm nach rechts und 20mm nach oben versetzt 5 tief` |
| B2 | Abstand von Kanten | `oben eine 10mm bohrung von der oberen kante 20mm und von rechter kante 30mm entfernt 5 tief` |
| B3 | Mischung Achsen (Versatz + Abstand) | `oben eine bohrung 10mm von links, 5mm aus mitte nach unten, d10 5 tief` |
| B4 | Skalierung viele (8+) | mehrere B1/B2-Bohrungen kombiniert |

### M — Lochmuster (Bohrmuster)

| ID | Variation | Beispiel-Spec |
|----|-----------|---------------|
| M1 | An Ecken | `auf jeder ecke der oberen flaeche eine 8mm bohrung 10mm von den kanten 5 tief` |
| M2 | Reihe Start+End | `5 bohrungen d10 in einer reihe von links 10mm bis rechts 10mm 5 tief` |
| M3 | Reihe Start+Abstand+Anzahl | `5 bohrungen d10 startend oben links 10mm von kanten, abstand 20mm, 5 tief` |

### N — Nuten (axial only, no rotation)

| ID | Variation | Beispiel-Spec |
|----|-----------|---------------|
| N1 | Aus Mitte | `oben eine nut 10x10 entlang z-achse 5mm nach rechts versetzt` |
| N2 | Von Kante | `oben eine nut 10x10 entlang z-achse von rechter kante 20mm entfernt` |

### T — Taschen

| ID | Variation | Beispiel-Spec |
|----|-----------|---------------|
| T1 | Versatz aus Mitte | `oben eine tasche 60x40x10 10mm nach rechts versetzt` |
| T2 | Abstand von Kanten | `oben eine tasche 60x40x10 von oben 20mm und links 30mm entfernt` |
| T3 | Rotiert | `oben tasche 60x40x10 um 20 grad gegen uhrzeigersinn gedreht` |
| T4 | Edge-zu-Edge (NICHT Center) | `oben tasche 30x20x10 deren rechte kante 25mm von rechter wuerfelkante entfernt` |

### E — Extrusionen (Wuerfel + Platte)

| ID | Variation | Beispiel-Spec |
|----|-----------|---------------|
| E1 | Center-Anchor (default) | `vorne platte 80x40x20 mit 80x40 flaeche aufliegend, zentriert` |
| E2 | Corner-Anchor (User-Konvention) | `vorne platte 80x40x20, obere rechte ecke der platte = obere rechte ecke der wuerfel-vorderseite` |
| E3 | Corner + Versatz | `E2 + 10mm nach links versetzt` |
| E4 | Edge-Anchor (Mitte) | `vorne platte, untere kante mittig auf der unteren wuerfelkante` |
| E5 | Mit Rotation | `E2 + 20 grad gegen uhrzeigersinn gedreht` |

### EF — Features auf Extrusion (Bohrung/Tasche/Nut auf Platte)

| ID | Variation | Beispiel-Spec |
|----|-----------|---------------|
| EF1 | Default-Flaeche | `auf der platte oben eine 5mm bohrung mittig 5 tief` |
| EF2 | Explizite Flaeche per Masse | `auf der 80x40 flaeche der platte eine 5mm bohrung mittig 5 tief` |
| EF3 | Default vs Nicht-Default | `auf der unteren 80x40 flaeche der platte eine bohrung` |

### NEST — Verschachtelte Features

| ID | Variation | Beispiel-Spec |
|----|-----------|---------------|
| NEST1 | Bohrung in Tasche | `oben tasche 60x40x10, in der tasche oben rechts d10 von kanten 10mm 5 tief` |
| NEST2 | Nut in Tasche (TBD) | (vermutlich noch nicht integriert) |

## User-Konventionen die in Goldens fixiert werden

Aus Memory + Diskussion 2026-05-08:

1. **Sicht auf die Seite (Anchor-Konvention)**: User benennt Punkte aus
   Sicht von AUSSEN auf die jeweilige Seite. "Obere rechte Ecke der
   Vorderseite" = Ecke aus Draufsicht-AUF-die-Vorderseite.

2. **AxB-Konvention**: erste Zahl in "AxB" geht horizontal (rechts in
   der Sicht), zweite vertikal (unten).

3. **Default-Flaeche bei Extrusionen**: Wenn User "auf der platte" sagt
   ohne Flaechen-Spezifikation: erste in der Spec genannte Auflage-Flaeche
   gilt als Default. Bei `platte 80x40x20 ... auf der platte` mit
   `auflage 80x40` → Default ist die obere 80x40 Flaeche.

4. **Default-Teil-Zuweisung**: Aktions-Phrasen ohne expliziten
   Teil-Bezug gehen auf das **Basis-Teil** (erstes Teil im Inventar,
   meist Wuerfel). Bug D — `aktions_splitter._assign_teil_id`.
   Override durch explizites "auf der platte X".

5. **Anchor: Kind-Ecke auf Parent-Kante**: Default-Regel ist Mitte der
   Kante. Endpunkt nur wenn User explizit "am unteren Ende der Kante"
   o.ae. sagt. Bug C in ADR 0004 dazu.

6. **"10mm nach oben versetzt" mit Rotation (offen, Bug E)**: Aktuell
   Corner-Pinned-After-Rotation Math → Plate-Centroid wandert nach unten.
   User erwartet: Centroid bleibt da wo er ohne Rotation waere (Anchor-
   then-Rotate). **Noch nicht entschieden.** Diskussion in neuem Chat.

## Architektur-Pivot (verschoben)

User-Idee: Spezialisten-Fan-Out (Bohrungs-Sucher, Taschen-Sucher,
Nuten-Sucher etc. parallel statt linearer Pipeline). Bewertung in
Diskussion vom 2026-05-08:

**Pro:** modular, jede Spezialist-Aufgabe winzig + DSPy-trainierbar,
neue Feature-Typen = neuer Spezialist.

**Con:** mehr LLM-Calls, Aggregation komplex, Cross-Output-Referenzen
(z.B. "in der Tasche eine Bohrung" — Bohrungs-Spezialist muss wissen
welche Tasche).

**Entscheidung:** Pivot **erst NACHDEM** Goldens-Baseline steht.
Sonst doppelte Arbeit (alte Architektur fixen + neue bauen ohne
Sicherheitsnetz). Sequenz:

1. Goldens-Baseline aufbauen (Layer 1 + 2)
2. Aktuelle rote Felder isoliert fixen mit Schutz
3. **Erst dann** Architektur-Pivot mit Goldens als Sicherheitsnetz
4. **Erst nach Pivot** DSPy-Training (sonst Moving Target)

## DSPy-Training-Konventionen (zukuenftig)

Pro Trainings-File ein klarer Header mit Scope:

```python
# === Training: <Agent-Name> ===
# Scope: <was wird genau trainiert? z.B. "Anchor-Punkt fuer extrudierte
#         Flaechen", "Pocket-mit-Bohrung-Verschachtelung">
# Coverage: <welche Spec-Patterns abgedeckt sind>
# Last-trained: <Datum, Modell, Reward>
# Examples: <Anzahl>
```

Pro Scope eine eigene Datei. Partielles Re-Training moeglich wenn nur
ein Aspekt schlechter wird.

**Aktueller Status (Inventar):**
- Mit DSPy-Demos: inventar, punctuation, aktions_klassifizierer,
  position_extractor, normalizer, position_normalizer (platzierer),
  assembly, pocket_child_placer
- Ohne DSPy: text_splitter, interpreter, validator, code_fixer, visioner
- **Tatsaechlich trainiert (optimierter Prompt):** position_extractor.
  Alle anderen laden nur Demos, kein optimierter Prompt aktiv.

## Naechste konkrete Schritte (fuer neuen Chat)

### Phase 0 — Mock-Replay-Infrastruktur (DONE in diesem Commit)

- `tests/golden/components/_helpers.py` — Resolver/Splitter-Replay
- 2 Beispiel-Component-Goldens: B1 (Bohrung Versatz) + B2 (Bohrung
  Kanten-Abstand)
- Pattern-Doku in `tests/golden/components/README.md`

### Phase 1 — Component-Goldens-Coverage (User + Claude gemeinsam)

User schickt Spec-Variationen pro Feature (B1-B4, M1-M3, N1-N2, T1-T4,
E1-E5, EF1-EF3, NEST1). Claude:

- Pro Variation: bestimme erwartetes resolved-Blueprint-Snippet (Resolver-
  Mathe nachrechnen).
- Pro Variation: erweitere Component-Golden.

Akzeptanz-Kriterium: alle Component-Goldens gruen.

### Phase 2 — Pipeline-Goldens mit Variationen

User schickt 2-3 Wording-Variationen pro Feature. Claude:

- Erstelle `tests/golden/<scope>/spec.v1.txt`, `v2.txt`, `v3.txt`
- Erwartetes Blueprint einmal aus echtem Run aufgenommen, fuer alle
  Variationen identisch.
- Real-Pipeline-Run pro Variation, Vergleich gegen Erwartung.

Akzeptanz-Kriterium: alle Variationen produzieren identisches
Blueprint (im Rahmen der Toleranzen).

### Phase 3 — Rote Felder isoliert fixen

Aus den letzten Real-Runs (944d6485, 5394bf3e, 9cfa059c, 1df15dfe,
94781bdd) jeweils ein Pipeline-Golden machen. Wenn rot: bewusste Fix-
Entscheidung mit Goldens-Schutz.

### Phase 4 — Architektur-Pivot (spaeter)

Spezialisten-Fan-Out Prototyp parallel zur bestehenden Pipeline.
Vergleichs-Run gegen Goldens. Wenn Spezialisten besser → Switch.

### Phase 5 — DSPy-Training (spaeter)

Pro Spezialist trainieren mit dem strukturierten Training-File-Format.

## Konkrete erste Aufgaben (User-Aktion fuer neuen Chat)

User schickt im neuen Chat:

1. **Spec-Variationen fuer B1-B3** (jeweils 2-3 Wordings pro Feature).
2. **Bestaetigung von Bug E** (Plate-Position mit Rotation):
   - Soll "10mm nach oben" den Plate-Centroid 10mm ueber Mitte landen
     (Anchor-then-Rotate)?
   - Oder Corner-Pinned bleibt richtig und das Verhalten wird
     dokumentiert (User akzeptiert Centroid-Wandern)?
3. **9cfa059c-Trace zur Bestaetigung Bug-D-Regression**: einmal kurz
   pruefen ob die Platte-Features wirklich durch Bug D verlorengingen.

Claude im neuen Chat startet mit:

1. Diesen ADR lesen.
2. `tests/golden/components/` ansehen + verstehen.
3. Phase 1 anfangen sobald User Variationen schickt.
