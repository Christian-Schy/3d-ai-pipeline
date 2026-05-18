# 24 — Pattern (Lochmuster: Grid / Kreis / Linear-Reihe)

## Konvention

Patterns sind **Anordnungen mehrerer Kind-Features** (heute praktisch immer
Bohrungen, theoretisch auch Taschen) nach einer geometrischen Regel.
Bemassung erfolgt auf **zwei Ebenen**:

1. **Pattern-Center / -Anchor** — wo liegt der Mittelpunkt des Patterns
   auf der Face? Volle DIN-Methodik A1-A6 anwendbar.
2. **Pattern-interne Geometrie** — Rasterabstand, Teilkreis-Durchmesser,
   Linear-Abstand, Anzahl, Pattern-Rotation. Diese Werte beschreiben
   wie die Kind-Features relativ zum Pattern-Center liegen.

Die **Kind-Features selbst** (z.B. einzelne Bohrungen) **erben** ihre
Position aus der Pattern-Regel — sie haben keine eigenen `abstand_*`-Werte.

### Drei Pattern-Typen

| Typ | Schema-Feld | Geometrie-Parameter |
|---|---|---|
| **Grid** (Raster n×m) | `hole_pattern_grid` | `rows`, `cols`, `spacing_x`, `spacing_y` |
| **Kreis** (Teilkreis) | `hole_pattern_circular` | `count`, `pitch_diameter`, optional `start_angle_deg` |
| **Linear-Reihe** | `hole_pattern_linear` | `count`, `spacing`, `direction` (x/y) |

Relevante Matrix-Zellen fuer Pattern-Center (siehe [`11_coverage_matrix.md`](11_coverage_matrix.md)):
**A1, A3, A4, A6** × **B0, B1, B2, B3** × **C0, C2, C3** × **D1, D2**.
A2 (`kante_*`) ist fuer point-like Pattern-Center **nicht** anwendbar
(analog Bohrung).

**A5 ≡ A1 fuer Kreis-Pattern.** Der Teilkreis-Mittelpunkt ist point-like.
"In der oberen rechten Ecke, X mm versetzt" heisst fuer einen Punkt
schlicht: Center X mm von zwei Kanten — also `abstand_*` (A1). A5 ist
damit fuer Kreis-Pattern **kein eigener Fall**, sondern wird als A1
modelliert (genau wie A5 fuer die Bohrung in Konvention 20 entfaellt).
Fuer Grid/Linear ist A5 ungetestet und derzeit nicht benoetigt.

### A1-Bezugspunkt — Pattern-Typ-abhaengig (DIN-konstrukteurnah)

Anders als bei Bohrung/Tasche/Slot (Konvention `abstand_*` = edge-to-CENTER
fuer point-like Features) trennt Pattern den A1-Bezugspunkt nach Typ:

| Pattern-Typ | A1 `abstand_*` Bezug | Begruendung |
|---|---|---|
| **Grid** | **Outermost-Hole** | Konstrukteur denkt "Bohrung X mm vom Rand", nicht "virtueller Mittelpunkt". |
| **Linear-Reihe** | **Outermost-Hole** | Gleicher Konstrukteur-Reflex; bei Achsenrichtung der Reihe die aeusserste Bohrung. |
| **Kreis (Teilkreis)** | **Pattern-Center** | Teilkreis-Mittelpunkt ist physikalisch und DIN-konventionell **der** Bezugspunkt. |

Konkret bei Grid/Linear bedeutet das: `abstand_links=18` bei `Lochmuster 3x3,
Rasterabstand 30` setzt die *linkeste* Bohrung 18mm vom linken Rand. Pattern-
Center sitzt dann bei `-W/2 + 18 + (cols-1)*spacing_x/2`. Analog Y.
A3 (`versatz_*` aus Mitte) referenziert weiterhin den **Pattern-Center**
— Center-relativ, nicht Edge-relativ. A5 fuer Kreis-Pattern wird als A1
(`abstand_*` zum Pattern-Center) modelliert, siehe oben.

## Wording-Beispiele

### Pattern-Typ Erkennung (Klassifizierer)

| Phrase | Typ |
|---|---|
| "Lochmuster 4x3", "Raster 5x2", "Grid 3x4" | **Grid** |
| "Kreismuster aus 6 Bohrungen", "Teilkreis Ø40 mit 8 Bohrungen", "Lochkreis 6x Ø5" | **Kreis** |
| "Reihe aus 5 Bohrungen", "5 Bohrungen entlang X im Abstand 20mm" | **Linear-Reihe** |

### Grid-spezifische Geometrie

| Phrase | Schema |
|---|---|
| "Lochmuster 4x3, Rasterabstand 25mm" | `rows: 4, cols: 3, spacing_x: 25, spacing_y: 25` |
| "Lochmuster 4x2 mit Rasterabstand 20mm in X und 30mm in Y" | `rows: 4, cols: 2, spacing_x: 20, spacing_y: 30` |
| "Raster 3x3 mit 25mm Lochabstand" | gleichbedeutend mit "Rasterabstand 25mm" |

### Kreis-spezifische Geometrie

| Phrase | Schema |
|---|---|
| "Kreismuster aus 6 Bohrungen, Teilkreis-Durchmesser 40mm" | `count: 6, pitch_diameter: 40` |
| "Lochkreis 8x Ø6 auf TK40, beginnt bei 0°" | `count: 8, hole_diameter: 6, pitch_diameter: 40, start_angle_deg: 0` |

### Linear-Reihe-spezifische Geometrie

| Phrase | Schema |
|---|---|
| "Reihe aus 5 Bohrungen entlang X, Abstand 20mm" | `count: 5, spacing: 20, direction: "x"` |
| "5 Bohrungen entlang Y im Lochabstand 15mm" | `count: 5, spacing: 15, direction: "y"` |
| "4 Bohrungen verlaufen nach hinten, Abstand 25mm" | `count: 4, spacing: 25, direction: "y"` (Richtungs-Verb-Variante) |

### Pattern-Rotation (Grid + Linear)

| Phrase | Interpretation |
|---|---|
| "Lochmuster 3x2, um 15° gedreht, zentriert" | Pattern-Rotation +15° um Pattern-Center, Kind-Bohrungen wandern mit |
| "Reihe aus 4 Bohrungen, um 20° im Uhrzeigersinn gedreht" | Pattern-Rotation -20° |

Pattern-Rotation gilt **nur** fuer das Pattern als Ganzes. Die Kind-
Bohrungen selbst bleiben rotations-symmetrisch (sie haben keine eigene
Rotation, siehe [`20_bohrung_din.md`](20_bohrung_din.md)). Kreis-Pattern
hat statt Rotation den `start_angle_deg` Parameter.

## Edge-Cases

### Pattern ueberragt das Bauteil

Mit der A1-Outermost-Hole-Konvention fuer Grid/Linear ist Ueberlauf
durch `abstand_*` nicht mehr passiv moeglich — die aeusserste Bohrung
sitzt per Definition genau auf der angegebenen Distanz vom Rand. Ueberlauf
entsteht aber weiterhin:
- bei **A3** (`versatz_*` aus Mitte) wenn Center+Pattern-Half ueber den
  Rand hinausgeht,
- bei **Kreis** mit kleiner Distanz vom Rand und grossem Teilkreis. Der
  M09-Test wurde deshalb auf Teilkreis Ø20 mit 15mm Eck-Versatz
  korrigiert (Ø30/8mm ragte ~7mm ueber die 100x40-links-Face).

`coordinate_validator` Check 12 (`_check_pattern_child_bounds`, seit
2026-05-18) iteriert die Kind-Bohrungen pro Pattern (Grid/Linear/Kreis),
wendet Pattern-Rotation an und meldet WARNING pro Bohrung deren
`|center| + radius` ueber die Bauteilkante hinausgeht. Max 5
Einzelmeldungen, danach Aggregat. Komplementaer zu Check 10
`_check_pattern_spacing` (prueft den Pattern-Span gegen Parent-Dim).

### Asymmetrische Grids

Bei Grids mit ungerader Reihen- und gerader Spalten-Anzahl (oder umgekehrt)
ist das Pattern-Center **nicht** ein Bohrungs-Center, sondern liegt
zwischen Bohrungen. Das ist DIN-konform und vom Resolver korrekt
unterstuetzt.

### Kreis-Pattern: `start_angle_deg`-Vokabular

Der Konstrukteur nennt selten `start_angle_deg` explizit. Default sollte
0° sein (erste Bohrung bei 3-Uhr / +X). Wording wie "Lochkreis mit erster
Bohrung oben" sollte zu `start_angle_deg: 90` aufgeloest werden — ist
heute **nicht implementiert**, gehoert in Cov-4-STRESS.

### "Verlauft nach" / Richtungs-Verb auf Linear-Reihe

Linear-Reihe-Richtung kann statt `direction: "x"|"y"` auch durch
"verlaeuft nach hinten/rechts" ausgedrueckt werden. Analog zu Slot-
Richtungs-Wording (siehe [`21_nut_slot_din.md`](21_nut_slot_din.md)).
Klassifizierer/Normalizer muss beides erkennen.

## Code-Pfad

- **Klassifizierer (ADR 0009 — drei Sub-Agents):**
  [`data/prompts/prompt_classifier_grid.py`](../../data/prompts/prompt_classifier_grid.py)
  (Raster + Eckbohrungen),
  [`data/prompts/prompt_classifier_circular.py`](../../data/prompts/prompt_classifier_circular.py)
  (Lochkreis/Teilkreis),
  [`data/prompts/prompt_classifier_linear.py`](../../data/prompts/prompt_classifier_linear.py)
  (Bohrungsreihe) — je ein fokussierter Prompt mit Geometrie-Hints.
- **Feature-Builder:** [`src/tools/feature_builder.py`](../../src/tools/feature_builder.py)
  Branch `feature_type == "hole_pattern_grid"` / `_linear` / `_circular`.
- **Resolver:** [`src/tools/blueprint_resolver.py`](../../src/tools/blueprint_resolver.py)
  behandelt Pattern-Center wie ein Bohrungs-Center (point-like).
- **Templates:** [`src/codegen/templates.py`](../../src/codegen/templates.py)
  Pro Pattern-Typ ein Template, das die Kind-Bohrungen aus den Geometrie-
  Parametern aufzaehlt. `hole_pattern_grid` / `hole_pattern_linear` haben
  einen `angle`-Parameter fuer Pattern-Rotation C2/C3 (ADR 0012).

## Tests — Coverage-Matrix-abgeleitet

Bauteil fuer alle Tests: **Wuerfel 150x100x40** (X x Y x Z).
Pro Test pflegen wir **D1** + **D2**. Pattern-Typ pro Test in Klammern.

| ID | Face | Typ | Matrix-Zellen | D1 (Feature → Position) | D2 (Position → Feature) |
|---|---|---|---|---|---|
| **M01** | oben | Grid | A4, B0, C0 | "Wuerfel 150x100x40. Oben ein Lochmuster 4x3, Bohrungen Ø6 Tiefe 12, Rasterabstand 25mm, zentriert." | "Wuerfel 150x100x40. Oben zentriert ein Lochmuster 4x3 mit Bohrungen Ø6 Tiefe 12 und Rasterabstand 25mm." |
| **M02** | oben | Grid | A1, B2, C0 | "Wuerfel 150x100x40. Oben ein Lochmuster 4x2, Bohrungen Ø5 Tiefe 10, Rasterabstand 20mm, von linker Kante 15mm und von vorderer Kante 20mm." | "Wuerfel 150x100x40. Oben 15mm von linker Kante und 20mm von vorderer Kante ein Lochmuster 4x2 mit Ø5 Tiefe 10 und Rasterabstand 20mm." |
| **M03** | rechts | Kreis | A4, B0, C0 | "Wuerfel 150x100x40. Rechts ein Kreismuster aus 6 Bohrungen Ø4 Tiefe 8, Teilkreis-Durchmesser 40mm, zentriert." | "Wuerfel 150x100x40. Rechts zentriert ein Kreismuster aus 6 Bohrungen Ø4 Tiefe 8 auf Teilkreis Ø40." |
| **M04** | vorne | Linear | A1+A4, B1, C0 | "Wuerfel 150x100x40. Vorne eine Reihe aus 5 Bohrungen Ø6 Tiefe 10 entlang X, Abstand 20mm, mittig auf der Hoehe und 15mm von linker Kante." | "Wuerfel 150x100x40. Vorne mittig auf der Hoehe und 15mm von linker Kante eine Reihe aus 5 Bohrungen Ø6 Tiefe 10 entlang X im Abstand 20mm." |
| **M05** | unten | Grid | A6, C0 | "Wuerfel 150x100x40. Unten ein Lochmuster 3x3 mit Ø5 Tiefe 12 und Rasterabstand 30mm, jeweils 18mm vom unteren linken Rand." | "Wuerfel 150x100x40. Unten jeweils 18mm vom unteren linken Rand ein Lochmuster 3x3 mit Ø5 Tiefe 12 und Rasterabstand 30mm." |
| **M06** | oben | Grid | A4, B0, **C2** | "Wuerfel 150x100x40. Oben ein Lochmuster 3x2, Bohrungen Ø6 Tiefe 10, Rasterabstand 25mm, um 15° gedreht, zentriert." | "Wuerfel 150x100x40. Oben zentriert ein um 15° gedrehtes Lochmuster 3x2 mit Ø6 Tiefe 10 und Rasterabstand 25mm." |
| **M07** | hinten | Linear | A4+A1, B1, **C3** | "Wuerfel 150x100x40. Hinten eine Reihe aus 4 Bohrungen Ø5 Tiefe 8, Abstand 18mm, um 20° im Uhrzeigersinn gedreht, mittig auf der Breite und 12mm von oberer Kante." | "Wuerfel 150x100x40. Hinten mittig auf der Breite und 12mm von oberer Kante eine Reihe aus 4 Bohrungen Ø5 Tiefe 8 im Abstand 18mm, um 20° im Uhrzeigersinn gedreht." |
| **M08** | oben | Linear | A1, B2, C0 — Richtungs-Verb | "Wuerfel 150x100x40. Oben eine Reihe aus 4 Bohrungen Ø5 Tiefe 10, verlaeuft nach hinten, Abstand 20mm, von linker Kante 30mm und von vorderer Kante 20mm." | "Wuerfel 150x100x40. Oben 30mm von linker Kante und 20mm von vorderer Kante eine Reihe aus 4 Bohrungen Ø5 Tiefe 10, die nach hinten verlaeuft, Abstand 20mm." |
| **M09** | links | Kreis | A5 (=A1), C0 | "Wuerfel 150x100x40. Links ein Kreismuster aus 4 Bohrungen Ø4 Tiefe 8, Teilkreis-Durchmesser 20mm, in der oberen rechten Ecke der Seite, 15mm nach links und 15mm nach unten versetzt." | "Wuerfel 150x100x40. Links in der oberen rechten Ecke der Seite 15mm nach links und 15mm nach unten versetzt ein Kreismuster aus 4 Bohrungen Ø4 Tiefe 8 auf Teilkreis Ø20." |
| **M10** | oben | Grid | A1+A3, B3, C0 | "Wuerfel 150x100x40. Oben ein Lochmuster 3x2, Ø5 Tiefe 10, Rasterabstand 25mm in X und 20mm in Y, von linker Kante 30mm und 10mm aus Mitte nach hinten versetzt." | "Wuerfel 150x100x40. Oben 30mm von linker Kante und 10mm aus Mitte nach hinten versetzt ein Lochmuster 3x2 mit Ø5 Tiefe 10 und Rasterabstand 25mm in X / 20mm in Y." |

**Coverage-Check:**
- A1 ✓ (M02, M04, M07, M08, M10)
- A3 ✓ (M10)
- A4 ✓ (M01, M03, M04, M06, M07) — pur (M01, M03, M06) + single-axis (M04, M07)
- A5 ✓ (M09)
- A6 ✓ (M05)
- B0 ✓ (M01, M03, M06)
- B1 ✓ (M04, M07)
- B2 ✓ (M02, M08)
- B3 ✓ (M10)
- C0 ✓ (M01, M02, M03, M04, M05, M08, M09, M10)
- C2 ✓ (M06) — CCW +15°
- C3 ✓ (M07) — CW -20°
- D1+D2 pro Test ✓
- Pattern-Typen: **Grid** (M01, M02, M05, M06, M10), **Kreis** (M03, M09), **Linear-Reihe** (M04, M07, M08)
- Linear-Richtungs-Wordings: "entlang X" (M04, M07), "verlaeuft nach hinten" (M08)
- Anisotrope Rasterabstaende (X≠Y): M10 (25 in X / 20 in Y)

**Seiten-Verteilung:** oben 5x, unten 1x, vorne 1x, hinten 1x, links 1x, rechts 1x → alle 6 Seiten min. 1x.

## Referenzen

- **DIN EN ISO 129-1:2022-02** — Eintragung von Massen und Toleranzen
  (Primaer-Anker; loest die zurueckgezogene DIN 406 ab). Standardpraxis
  fuer Lochbilder: Teilkreis-Durchmesser + Anzahl + Winkel der ersten
  Bohrung (Kreis); Lochabstand + Anzahl + Position der aeussersten
  Bohrung (Grid/Linear).
- **DIN EN ISO 5459:2024** — Datums und Datum-Systeme; Pattern-Center
  bzw. Teilkreis-Mitte als potentielles Datum (relevant ab Cap 7.0).
- DIN 406 — historisch, zurueckgezogen (siehe
  [`99_normen_audit.md`](99_normen_audit.md)).
- Verkn. Konventionen: [`10_masseintragung_din406.md`](10_masseintragung_din406.md),
  [`11_coverage_matrix.md`](11_coverage_matrix.md), [`20_bohrung_din.md`](20_bohrung_din.md)

## Stand

Coverage-Matrix-abgeleitete Test-Liste (10 Spec-Paare = 20 Test-Cases) —
3 Pattern-Typen × 6 Seiten × A1-A6 × B0-B3 × C0/C2/C3.
Resolved-Blueprints werden pro Test ausgefuellt sobald User-Review der
Spec-Wordings abgeschlossen ist.
