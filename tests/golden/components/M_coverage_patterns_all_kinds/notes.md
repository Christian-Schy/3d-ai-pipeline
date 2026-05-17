# M_coverage_patterns_all_kinds — Pattern L2-Coverage-Golden

**Capability 1.0 — Pattern (Lochmuster: Grid / Kreis / Linear-Reihe).
Cov-3-Stufe ([CLAUDE.md](../../../../CLAUDE.md) "L2-Coverage-Goldens").**

Eine Capability komplett: alle drei Pattern-Typen, mehrere Seiten,
DIN-Wording-Varianten A1/A3/A4/A6 auf einem **Wuerfel 150x100x40**.

## Test-Faelle (aus [`docs/conventions/24_pattern_din.md`](../../../../docs/conventions/24_pattern_din.md))

10 Patterns — M01-M10, vollstaendig. Keine deferred Cases mehr.

| Feature | Face | Typ | Matrix-Zellen | DIN-Bezug |
|---|---|---|---|---|
| `m01_oben_grid_a4_b0` | oben | Grid | A4, B0 | zentriert, explizites Raster 4x3 |
| `m02_oben_grid_a1_b2` | oben | Grid | A1, B2 | edge-distance → outermost-Hole |
| `m03_rechts_kreis_a4_b0` | rechts | Kreis | A4, B0 | zentriert, Teilkreis |
| `m04_vorne_linear_a1_a4_b1` | vorne | Linear | A1+A4, B1 | edge-distance + zentriert |
| `m05_unten_grid_a6` | unten | Grid | A6 | "jeweils X von zwei Kanten" |
| `m06_oben_grid_c2` | oben | Grid | C2 | Pattern-Rotation CCW +15° |
| `m07_hinten_linear_c3` | hinten | Linear | A1+A4, C3 | Pattern-Rotation CW -20° |
| `m08_oben_linear_a1_b2_verb` | oben | Linear | A1, B2 | Richtungs-Verb "verlaeuft nach" |
| `m09_links_kreis_a5` | links | Kreis | A5 (=A1) | Face-Ecke + Versatz, point-like → edge-distance |
| `m10_oben_grid_a1_a3_b3` | oben | Grid | A1+A3, B3 | edge-distance + center-offset, anisotrop |

**Coverage-Check:**
- A1 ✓ (M02, M04, M07, M08, M10)
- A3 ✓ (M10)
- A4 ✓ (M01, M03, M04, M07)
- A5 ✓ (M09) — Kreis-Pattern-Center ist point-like, A5 ≡ A1
- A6 ✓ (M05)
- B0 ✓ (M01, M03)
- B1 ✓ (M04)
- B2 ✓ (M02, M08)
- B3 ✓ (M10)
- C2 ✓ (M06) — Grid-Rotation CCW +15°
- C3 ✓ (M07) — Linear-Rotation CW -20°
- Pattern-Typen: **Grid** (M01, M02, M05, M06, M10), **Kreis** (M03, M09),
  **Linear** (M04, M07, M08)
- Grid-Raster: 4x3, 4x2, 3x3, 3x2 — nicht-quadratisch, explizites
  Schema (`rows`/`cols`/`spacing_x`/`spacing_y`)
- Anisotropes Raster: M10 (25mm in X, 20mm in Y)
- Linear-Richtung: "entlang X" (M04), Richtungs-Verb (M08)
- A1 fuer Grid/Linear referenziert die **outermost-Hole** (Konvention 24)

## Status — Resolver-Golden gruen, Pipeline-Golden angelegt (ADR 0009)

Der resolver-component-test verifiziert die Pattern-Mathe fuer alle
7 Faelle deterministisch (gruen).

Seit ADR 0009 hat dieses Golden auch ein `pipeline/specs.txt` (D1+D2
Wording-Varianten). Der ueberladene `pattern_classifier` wurde in drei
fokussierte Sub-Klassifizierer gesplittet: `grid_classifier`,
`circular_classifier`, `linear_classifier` (ADR-0006-Mechanik). Der
`grid_classifier` trennt "explizites Raster" (Lochmuster NxM +
Rasterabstand → rows/cols/rasterabstand) von "Eckbohrungen" (NxM/
Eckbohrungen + Randabstand → anzahl/abstand_kante) — genau der Bug, der
beim alten Retrain M_kombo m02 regressiert hat.

**Adoptions-Sequenz:** Die drei Sub-Agents starten in
`config/config.yaml` mit `*_enabled: false`. Vor dem Pipeline-Real-Run:
`grid_classifier`/`circular_classifier`/`linear_classifier` trainieren
(`train_dspy.py`), Flags auf `true` setzen, dann
`make goldens-real-filter F=M` — inkl. M_kombo-Regressions-Check.

## Grid-Schema-Erweiterung

`hole_pattern_grid` unterstuetzt jetzt das explizite Schema
`{rows, cols, spacing_x, spacing_y}` zusaetzlich zur Legacy-Form
`{count, inset}`. "Lochmuster 4x3, Rasterabstand 25mm" wird nicht mehr
auf 2x2/3x2/3x3 gezwungen. Template `hole_pattern_grid` nimmt
`rows`/`cols`/`spacing` direkt (`.rarray`), der Assembler konvertiert
Legacy `count`/`inset` ueber `_grid_layout`. Der Resolver wendet
edge_distances beim expliziten Grid an (A1 outermost-Hole), beim
Legacy-Grid bleibt es bei `inset`-Zentrierung. Diese Geometrie-
Infrastruktur ist agenten-unabhaengig und ruekwaertskompatibel
(M_kombo Legacy-Grid bleibt gruen).

## Phase B — M09 aktiviert (2026-05-16)

Vorher deferred. Zwei Befunde, beide aufgeloest:

- **A5 fuer Kreis-Pattern ≡ A1.** Der Teilkreis-Mittelpunkt ist
  point-like (wie eine Bohrung). "In der oberen rechten Ecke, X mm
  versetzt" heisst fuer einen Punkt schlicht: Center X mm von zwei
  Kanten = `abstand_*` (edge-to-center). Genau die Logik, mit der
  Konvention 20 A5 fuer die Bohrung abgeschafft hat. M09 braucht **kein**
  Anker-Schema — es ist ein A1-Fall. Damit auch kein
  Resolver-Mirror-Face-Anker-Pfad noetig.
- **Geometrie korrigiert.** Konvention 24 M09 (Teilkreis Ø30, 8mm
  Versatz) ragte ~7mm ueber die 100x40-links-Face. Neu: Teilkreis Ø20,
  Versatz 15mm — Pattern-Center bei `abstand_rechts:15, abstand_oben:15`,
  Kreis + Bohrungen passen sicher (Konvention 24 entsprechend korrigiert).

## Phase C — M06 + M07 aktiviert (2026-05-16)

Vorher deferred. Pattern-Rotation (Konvention 24 C2/C3) ist jetzt
template-seitig implementiert (ADR 0012):

- `hole_pattern_grid` + `hole_pattern_linear` haben einen `angle`-
  Parameter. Grid: `.transformed(rotate=(0,0,angle))` vor `.rarray`
  (Raster rotiert um seinen Mittelpunkt). Linear: jede Bohrungs-Position
  wird um den Reihen-Mittelpunkt gedreht. `angle=0` bleibt
  bit-identisch zum Alt-Verhalten.
- Der Assembler reicht `placement.angle_deg` an beide Templates durch.
- `grid_classifier` + `linear_classifier` haben den `rotation_deg`-Hint
  (CCW positiv, CW negativ). Je 1 Klassifizierer- + 1 Normalizer-Demo.

Keine deferred Cases mehr in M_coverage — 10/10.

**Hinweis Spiegelflaeche:** M07 sitzt auf der hinten-Face (`>Y`, eine
Viewer-Spiegelflaeche). Der resolver-component-Test prueft nur
`placement.angle_deg` — die visuelle Dreh-Richtung im STL auf
Spiegelflaechen ist erst beim Real-Run/STL-Check verifizierbar.

## Resolver-Mathe

Wuerfel 150x100x40 → Face-Half:
- `>Z`/`<Z` (oben/unten): (75, 50) — `>Y`/`<Y`: (75, 20) — `>X`/`<X`: (50, 20)

Beispiel M02 (oben Grid 4x2, spacing 20, `edge_distances {left:15, vorne:20}`):
- Pattern-Footprint: span_x = (cols-1)*spacing_x = 1*20 = 20,
  span_y = (rows-1)*spacing_y = 3*20 = 60
- `left` outermost-Hole: ox = -(75 - 15 - 20/2) = **-50**
- `vorne` outermost-Hole: oy = -(50 - 20 - 60/2) = **0**

## Was dieser Test absichert (Resolver-Seite)

- Resolver-Math fuer Grid/Kreis/Linear-Patterns
- Explizites Grid-Raster `rows x cols` + Rasterabstand (auch anisotrop)
- A1-outermost-Hole-Konvention fuer Grid + Linear (Resolver-Math)
- Edge-distance / center-offset / Footprint-Subtraktion pro Pattern-Typ
- Multi-Feature-Aggregation auf einem Bauteil

`B_coverage`, `T_coverage`, `N_coverage` sind volle Pipeline-Goldens.
M_coverage hat seit ADR 0009 ebenfalls ein `pipeline/specs.txt` — der
Heatmap-PASS steht aus, bis die drei Pattern-Sub-Agents trainiert und
aktiviert sind (siehe Adoptions-Sequenz oben).
