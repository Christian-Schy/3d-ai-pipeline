# M_coverage_patterns_all_kinds — Pattern L2-Coverage-Golden

**Capability 1.0 — Pattern (Lochmuster: Grid / Kreis / Linear-Reihe).
Cov-3-Stufe ([CLAUDE.md](../../../../CLAUDE.md) "L2-Coverage-Goldens").**

Eine Capability komplett: alle drei Pattern-Typen, mehrere Seiten,
DIN-Wording-Varianten A1/A3/A4/A6 auf einem **Wuerfel 150x100x40**.

## Test-Faelle (aus [`docs/conventions/24_pattern_din.md`](../../../../docs/conventions/24_pattern_din.md))

7 Patterns — M01-M05, M08, M10. M06/M07/M09 deferred (siehe unten).

| Feature | Face | Typ | Matrix-Zellen | DIN-Bezug |
|---|---|---|---|---|
| `m01_oben_grid_a4_b0` | oben | Grid | A4, B0 | zentriert, explizites Raster 4x3 |
| `m02_oben_grid_a1_b2` | oben | Grid | A1, B2 | edge-distance → outermost-Hole |
| `m03_rechts_kreis_a4_b0` | rechts | Kreis | A4, B0 | zentriert, Teilkreis |
| `m04_vorne_linear_a1_a4_b1` | vorne | Linear | A1+A4, B1 | edge-distance + zentriert |
| `m05_unten_grid_a6` | unten | Grid | A6 | "jeweils X von zwei Kanten" |
| `m08_oben_linear_a1_b2_verb` | oben | Linear | A1, B2 | Richtungs-Verb "verlaeuft nach" |
| `m10_oben_grid_a1_a3_b3` | oben | Grid | A1+A3, B3 | edge-distance + center-offset, anisotrop |

**Coverage-Check:**
- A1 ✓ (M02, M04, M08, M10)
- A3 ✓ (M10)
- A4 ✓ (M01, M03, M04)
- A6 ✓ (M05)
- B0 ✓ (M01, M03)
- B1 ✓ (M04)
- B2 ✓ (M02, M08)
- B3 ✓ (M10)
- Pattern-Typen: **Grid** (M01, M02, M05, M10), **Kreis** (M03),
  **Linear** (M04, M08)
- Grid-Raster: 4x3, 4x2, 3x3, 3x2 — nicht-quadratisch, explizites
  Schema (`rows`/`cols`/`spacing_x`/`spacing_y`)
- Anisotropes Raster: M10 (25mm in X, 20mm in Y)
- Linear-Richtung: "entlang X" (M04), Richtungs-Verb (M08)
- A1 fuer Grid/Linear referenziert die **outermost-Hole** (Konvention 24)

## Status — Resolver-Golden, Pipeline-Test pending grid_classifier

Dieses Golden ist aktuell **resolver-only** (kein `pipeline/specs.txt`).
Der resolver-component-test verifiziert die Pattern-Mathe fuer alle
7 Faelle deterministisch (gruen).

Der Pipeline-Real-Run-Test ist noch nicht beigelegt: der heutige
`pattern_classifier` ist ueberladen — er deckt Grid + Kreis + Linear in
einem Prompt ab und kann "explizites Grid (Lochmuster NxM + Rasterabstand
→ rows/cols)" nicht sauber von "Eckbohrungen (NxM Lochmuster +
Randabstand → count/inset)" trennen. Ein Retrain mit NxM-Traces hat
M_kombo m02 regressiert (das Eckbohrungs-2x2 wurde faelschlich als
explizites Grid gelesen). Loesung: ein dedizierter **grid_classifier**
Sub-Agent (ADR-0006-Mechanik wie hole/pocket/slot/pattern/edge_feature)
mit fokussiertem Prompt. Eigener Arbeitsblock — siehe Memory
`project_grid_classifier_subagent`.

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

## Bekannte Limitierungen — M06 + M07 + M09 deferred

- **M06 (Grid-Rotation) + M07 (Linear-Rotation)** — die Pattern-Templates
  (`hole_pattern_grid`, `hole_pattern_linear`) erzeugen ein achsen-
  paralleles Raster ohne Rotations-Parameter. Pattern-Rotation als
  Ganzes (Konvention 24 C2/C3) ist noch nicht template-seitig
  implementiert. Braucht einen Rotations-Parameter im Template.
- **M09 (A5-Anker fuer Kreismuster)** — der Pattern-Klassifizierer hat
  kein Anker-Konzept im Schema. A5 ist fuer Pattern valide (Pattern hat
  einen Center, der auf eine Bauteil-Face-Ecke gesetzt werden kann);
  braucht Klassifizierer-Schema-Erweiterung. Zusaetzlich ueberlaeuft
  M09 geometrisch (Teilkreis Ø30 + 8mm Eck-Versatz auf 100x40-Face).

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
M_coverage ist resolver-only bis der `grid_classifier`-Sub-Agent steht.
