# ADR 0012 — Pattern-Rotation (Grid + Linear)

- **Datum:** 2026-05-16
- **Status:** accepted
- **Vorgaenger-ADRs:** 0009 (Pattern-Split), 0010/0011 (Phase-B-Schema)
- **Verwandt:** Konvention 24 (C2/C3), Golden `M_coverage` M06/M07,
  `project_next_phase_plan` (Phase C)

## Problem

M06/M07 (Konvention 24, Matrix-Zellen C2/C3) waren deferred:
"Lochmuster 3x2, um 15° gedreht" / "Reihe aus 4 Bohrungen, um 20° im
Uhrzeigersinn gedreht". Die Templates `hole_pattern_grid` /
`hole_pattern_linear` erzeugen ein achsen-paralleles Muster und
ignorieren jede Rotation.

## Befund

Der Rotationswinkel ist **kein Schema-Problem**. `feature_builder` liest
`drehung`/`rotation_deg` bereits in `position.angle_deg` (fuer alle
Feature-Typen), der Resolver reicht ihn als `placement.angle_deg`
durch — verifiziert per Dry-Run fuer `hole_pattern_grid`. Die Luecke ist
rein template-seitig plus der Assembler-Aufruf.

## Entscheidung

1. **Templates** bekommen einen `angle`-Parameter:
   - `hole_pattern_grid`: `.center(ox,oy).transformed(rotate=(0,0,angle))
     .rarray(...)` — die `.rarray` legt die Punkte im gedrehten
     Workplane-Frame aus, das Raster rotiert um seinen Mittelpunkt.
     Gleiche Mechanik wie `pocket_rect` mit `.transformed(rotate=...)`.
   - `hole_pattern_linear`: jede Bohrungs-Position wird um `angle` um den
     Reihen-Mittelpunkt gedreht — row-lokal `(pos, 0)` →
     `(pos·cosα, pos·sinα)` bzw. fuer Richtung y `(-pos·sinα, pos·cosα)`.
2. **Assembler** uebergibt `placement.angle_deg` an beide
   Template-Aufrufe (`hole_pattern_grid` / `hole_pattern_linear`).
3. **Klassifizierer**: `rotation_deg`-Hint zu `grid_classifier` +
   `linear_classifier` (Schema + Prompt). CW = negativ, CCW = positiv —
   gleiche Konvention wie Pocket/Slot.
4. **Kein Schema-, kein Resolver-Change.** `angle_deg` ist bereits im
   `placement`-Schema.

## Verworfen

- **Per-Bohrung-Rotation** — die Kind-Bohrungen sind rotations-
  symmetrisch (rund); nur das Muster als Ganzes rotiert (Konvention 24).
- **Circular-Pattern-Rotation** (`start_angle_deg`) — kein M-Testfall,
  Konvention 24 nennt es separat; out of scope.

## Risiko & Gegenmittel

Das `hole_pattern_linear`-Template hat eine bestehende Vorzeichen-
Eigenheit im per-Bohrung-`.center()`-Ausdruck. Der `angle=0`-Pfad muss
bit-identisch bleiben — M04/M08/M_kombo m05 duerfen nicht regressieren.
Gegenmittel: Rotation wird additiv aufgesetzt, `angle=0` faellt
explizit auf den bestehenden Ausdruck zurueck.

## Konsequenzen

- M06/M07 aktivierbar; M_coverage 10/10 vollstaendig.
- Pattern-Rotation steht damit auch fuer L3-STRESS-Goldens bereit.
