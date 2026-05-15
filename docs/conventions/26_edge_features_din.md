# 26 — Edge Features (Fase / Rundung)

## Konvention

Fasen (`chamfer`) und Rundungen (`fillet`) sind **Modifikationen** auf
Bauteil-Kanten — sie haben keine Position auf einer Face, sondern eine
**Kanten-Auswahl** und einen **Groessen-Parameter**. Bemassung erfolgt
auf zwei Ebenen:

1. **Kanten-Auswahl** — welche der 12 Kanten eines Wuerfels (bzw. der
   Kanten eines beliebigen Bodies) sollen modifiziert werden?
2. **Groesse** — Fase: Kantenlaenge (DIN: "Cx" = x mm × 45° oder "x × 45°").
   Rundung: Radius (DIN: "Rx").

Anders als bei Bohrung/Tasche/Slot/Pattern gibt es **keine** A1-A6-DIN-
Methodik — Position ist durch die Kanten-Auswahl bereits vollstaendig
bestimmt. Relevante Matrix-Zellen reduzieren sich auf **E0-E5** (Kanten-
Auswahl) × **F1-F2** (Groessen-Wording).

| E | Kanten-Auswahl | CadQuery `edges()` |
|---|---|---|
| **E0** | alle Kanten | `""` (no selector) |
| **E1** | alle vertikalen Kanten (parallel Z) | `"\|Z"` |
| **E2** | alle horizontalen Kanten | `"\|X or \|Y"` |
| **E3** | obere/untere Kanten der Top-/Bottom-Face | `">Z"` / `"<Z"` |
| **E4** | Kanten einer Seitenflaeche | `">Y"`, `"<Y"`, `">X"`, `"<X"` |
| **E5** | einzelne Kante (z.B. "vordere obere Kante") | `">Y and >Z"` etc. |

F1/F2: F1 = Fase (Groesse als Kantenlaenge), F2 = Rundung (Groesse als
Radius). Mischformen E0×F1+F2 (z.B. "obere Kanten verrundet, untere
gefast") sind Multi-Feature-Cases.

## Wording-Beispiele

### Fase

| Phrase | Schema |
|---|---|
| "Fase 2mm an allen Kanten" | `typ: fase, groesse: 2, edge_selector: ""` |
| "Alle vertikalen Kanten fasen mit 3mm" | `typ: fase, groesse: 3, edge_selector: "\|Z"` |
| "C2 an den oberen Kanten" | `typ: fase, groesse: 2, edge_selector: ">Z"` (DIN-Kurzschreibweise C2 = 2x45°) |
| "Fase 2x45° an den vier vertikalen Kanten" | `typ: fase, groesse: 2, edge_selector: "\|Z"` (Winkel 45° ist DIN-Default) |
| "Vordere obere Kante 5mm gefast" | `typ: fase, groesse: 5, edge_selector: ">Y and >Z"` |

### Rundung

| Phrase | Schema |
|---|---|
| "Rundung R3 an allen Kanten" | `typ: rundung, radius: 3, edge_selector: ""` |
| "Alle vertikalen Kanten R5 verrunden" | `typ: rundung, radius: 5, edge_selector: "\|Z"` |
| "Oberkanten der Front mit R2 abrunden" | `typ: rundung, radius: 2, edge_selector: ">Y and >Z"` |
| "die Außenkanten der Oberseite mit Radius 4" | `typ: rundung, radius: 4, edge_selector: ">Z"` |
| "Verrundung 6mm auf der Vorderseite" | `typ: rundung, radius: 6, edge_selector: ">Y"` (alle 4 Kanten der >Y-Face) |

### Kanten-Auswahl-Vokabular

| Phrase | edge_selector | E-Klasse |
|---|---|---|
| "alle Kanten" / "ringsum" / "rundum" | `""` | E0 |
| "vertikale Kanten" / "Hochkanten" / "stehende Kanten" | `"\|Z"` | E1 |
| "horizontale Kanten" / "liegende Kanten" | `"\|X or \|Y"` | E2 |
| "obere Kanten" / "Oberkanten" | `">Z"` | E3 |
| "untere Kanten" / "Unterkanten" | `"<Z"` | E3 |
| "Vorderseite" / "vorne" + Kanten | `">Y"` | E4 |
| "Rueckseite" / "hinten" + Kanten | `"<Y"` | E4 |
| "rechte Seite" / "rechts" + Kanten | `">X"` | E4 |
| "linke Seite" / "links" + Kanten | `"<X"` | E4 |
| "vordere obere Kante" / "Frontoberkante" | `">Y and >Z"` | E5 |
| "hintere obere Kante" | `"<Y and >Z"` | E5 |
| "vordere rechte (vertikale) Kante" | `">Y and >X"` | E5 |

## Edge-Cases

### Reihenfolge bei Mehrfach-Modifikationen

Fasen/Rundungen werden in Build-Order angewandt. "Erst alle Kanten R3
verrunden, dann obere Kanten 2mm fasen" funktioniert nicht — die obere
Kante existiert nach dem Verrunden nicht mehr als scharfe Kante. Der
`coordinate_validator` warnt nicht aktiv dafuer; `coder_knowledge` RAG
hat einen Hinweis. **Empfehlung im Wording**: Fasen vor Rundungen, oder
disjunkte Kanten-Auswahlen.

### Innenkanten von Taschen/Slots

`.edges("X")` auf einem Body trifft **alle** Kanten — auch die innen
liegenden Tasche-/Slot-Kanten. Das ist meistens **nicht** gewollt:
"Außenkanten der Oberseite fasen" bedeutet die 4 Außenkanten der
Top-Face, nicht zusaetzlich die 4 Tasche-Kanten. Der Edge-Feature-
Classifier soll "Außenkanten" als Selektor-Hinweis erkennen und der
Template kann via `>Z and not (...)` filtern — heute **noch nicht
implementiert**, gehoert in Cov-4-STRESS.

### "C2" vs "Fase 2mm" — DIN-Kurzschreibweise

DIN 6784 erlaubt "Cx" als Abkuerzung fuer eine 45°-Fase mit
Kantenlaenge x. Der Classifier muss "C2", "C 2", "C2x45°" als
aequivalent zu "Fase 2mm" erkennen. Synonym-Tabelle im Classifier-Prompt
deckt das ab; Wording-Pool sollte mindestens je eine Variante pro
Synonym in den Demos haben.

### Symmetrie-Annahmen

DIN-Konstrukteur erwartet **gleiche Fase** auf gegenueberliegenden
Kanten implizit, **wenn** der Wortlaut Symmetrie nahelegt ("vorne und
hinten oben gefast 2mm" → beide Frontoberkanten). Wenn das Wort
"jeweils" auftaucht ("jeweils 2mm an oben und unten"), ist's eindeutig
beidseitig. Bei Asymmetrie ("oben 2mm, unten 3mm") muss der Classifier
das als zwei separate Aktionen extrahieren.

### Asymmetrische Fasen (Cx×y, Winkel != 45°)

DIN erlaubt "Fase 2×3 mm" (asymmetrische Fase, 2mm in eine Richtung,
3mm in die andere) und "Fase 2 mm × 30°" (anderer Winkel als 45°).
CadQuery `.chamfer(length, length2=None)` unterstuetzt asymmetrisch,
braucht aber Edge-Auswahl mit definierter Richtung. **Aktuell nicht
implementiert** — Template `chamfer` nimmt nur einen Groessen-Parameter
(symmetrisch 45°). Gehoert in Capability 7.0 (Engineering Norms).

## Code-Pfad

- **Klassifizierer:** [`data/prompts/prompt_classifier_edge_feature.py`](../../data/prompts/prompt_classifier_edge_feature.py)
  — erkennt Typ (fase/rundung) + Groesse aus einer Aktions-Phrase.
  **TODO:** Edge-Selector-Erkennung aus Phrase ableiten (aktuell
  default `|Z`).
- **Feature-Builder:** [`src/tools/feature_builder.py`](../../src/tools/feature_builder.py)
  Branch `feature_type in ("fillet", "chamfer")` — extrahiert `radius`
  bzw. `size` aus Hints, mappt Kanten-Auswahl-Wording auf `edge_selector`.
- **Resolver:** [`src/tools/blueprint_resolver.py`](../../src/tools/blueprint_resolver.py)
  Edge-Features brauchen **keinen** Resolver-Schritt (kein
  Pattern-Center, kein face-aware Offset) — Resolver setzt sie direkt
  durch.
- **Templates:** [`src/codegen/templates.py`](../../src/codegen/templates.py)
  `fillet(radius, edge_selector)` und `chamfer(size, edge_selector)`.
- **Coder-Pfad:** **nicht** verwenden. Beide Operationen sind 100%
  templatebar; Coder-Aktivierung waere ein Regress
  (siehe `feedback_template_mode_no_coder.md`).

## Tests — Coverage-Matrix-abgeleitet

Bauteil fuer alle Tests: **Wuerfel 100x60x40** (X x Y x Z) — drei
distinkte Dimensionen damit "obere", "vordere", "rechte" Kanten
eindeutig sind. Pro Test pflegen wir **D1** + **D2**.

| ID | Typ | E-Klasse | F | D1 (Feature → Wording) | D2 (Position → Feature) |
|---|---|---|---|---|---|
| **F01** | Fase | E0 | F1 | "Wuerfel 100x60x40. Alle Kanten mit Fase 2mm." | "Wuerfel 100x60x40, ringsum gefast 2mm." |
| **F02** | Fase | E1 | F1 | "Wuerfel 100x60x40. Die vier vertikalen Kanten mit Fase 3mm." | "Wuerfel 100x60x40, an den vertikalen Kanten C3." |
| **F03** | Fase | E3 | F1 | "Wuerfel 100x60x40. Die oberen Kanten gefast 2mm." | "Wuerfel 100x60x40 mit Oberkanten C2." |
| **F04** | Fase | E5 | F1 | "Wuerfel 100x60x40. Vordere obere Kante mit Fase 5mm." | "Wuerfel 100x60x40, an der Frontoberkante 5mm gefast." |
| **F05** | Rundung | E0 | F2 | "Wuerfel 100x60x40. Alle Kanten verrundet R3." | "Wuerfel 100x60x40 ringsum mit Radius 3 abgerundet." |
| **F06** | Rundung | E1 | F2 | "Wuerfel 100x60x40. Die vertikalen Kanten mit Radius 5 verrundet." | "Wuerfel 100x60x40, an den Hochkanten R5." |
| **F07** | Rundung | E3 | F2 | "Wuerfel 100x60x40. Die oberen Kanten mit Rundung R2." | "Wuerfel 100x60x40 mit Oberkanten-Rundung 2mm." |
| **F08** | Rundung | E4 | F2 | "Wuerfel 100x60x40. Die Kanten der Vorderseite mit R4 abrunden." | "Wuerfel 100x60x40, vorne ringsum R4." |
| **F09** | Fase+Rundung | E1+E3 | F1+F2 | "Wuerfel 100x60x40. Vertikale Kanten C2, obere Kanten R3." | "Wuerfel 100x60x40 mit Fase 2mm an den vertikalen Kanten und Rundung R3oben." |
| **F10** | Fase | E5 (asymm) | F1 | "Wuerfel 100x60x40. Vordere obere Kante 3mm, hintere obere Kante 1mm gefast." | "Wuerfel 100x60x40 mit Frontoberkante 3mm und Hinteroberkante 1mm Fase." |

**Coverage-Check:**
- E0 ✓ (F01, F05)
- E1 ✓ (F02, F06, F09)
- E2 ⨯ — TBD (separater Test fuer "horizontale Kanten")
- E3 ✓ (F03, F07, F09)
- E4 ✓ (F08)
- E5 ✓ (F04, F10) — einzelne Kante + asymmetrische Mehrfach-Auswahl
- F1 (Fase) ✓ (F01-F04, F09, F10)
- F2 (Rundung) ✓ (F05-F09)
- F1+F2 Mischformen ✓ (F09)
- DIN-Kurzform "Cx" ✓ (F02, F03, F09)
- Multi-Aktion asymmetrisch ✓ (F10)
- D1+D2 pro Test ✓

**Verteilung Kanten-Auswahl:** alle Kanten 2x, vertikal 3x, oben/unten 3x, Face-Kanten 1x, Einzelkante 2x.

## STRESS-Erweiterung (Cov-4)

Edge-Features sollen in den STRESS-Multi-Feature-Tests vorkommen, weil
sie typische Konstrukteur-Endbearbeitung sind. Vorgeschlagene
Integration in `STRESS_all_in_one_part` und `STRESS_multi_plate_with_features`:

- **STRESS_all_in_one_part:** Grundwuerfel mit Bohrungen + Pockets +
  Slots + Pattern bekommt zusaetzlich:
  - Alle vertikalen Kanten C2 (E1+F1)
  - Obere Außenkanten R3 (E3+F2)
  - Eine einzelne Schluesselkante 5mm gefast (E5+F1)
- **STRESS_multi_plate_with_features:** Jede Platte mit eigener
  Fase/Rundung — Frontkanten der Basisplatte gerundet, vertikale Kanten
  der aufgesetzten Platte gefast.

## Referenzen

- DIN 6784 — Werkstuecke aus Metall, Kantenform und -masse
- DIN ISO 13715 — Werkstueck-Kanten (unbestimmte Form)
- ISO 13715 — Edges of undefined shape
- Verkn. Konventionen: [`10_masseintragung_din406.md`](10_masseintragung_din406.md),
  [`11_coverage_matrix.md`](11_coverage_matrix.md)

## Stand

Konventions-Doc neu (2026-05-15). Coverage-Matrix-abgeleitete Test-Liste
(10 Spec-Paare = 20 Test-Cases) — analog zu Bohrung/Tasche/Pattern. Die
Goldens (F01-F10 als Component-Goldens) und STRESS-Integration kommen
parallel zu Capability 2.0 (siehe CLAUDE.md Capability-Matrix). Resolver
braucht keinen Eingriff — Edge-Features sind point-frei und gehen direkt
zum Template.
