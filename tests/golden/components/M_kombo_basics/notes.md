# M_kombo_basics — 6 Pattern-Variationen auf 100mm Wuerfel

Stress-Test fuer Lochmuster-Resolver-Pfad. Drei Pattern-Typen:
- hole_pattern_grid: NxM Raster (.rarray)
- hole_pattern_circular: Lochkreis (.polarArray)
- hole_pattern_linear: Reihe mit Spacing

**Kritischer Code-Pfad: Grid-Bypass.** `_resolve_feature:1212-1216`
forciert edge_distances/pocket_edge_distances auf None fuer
`hole_pattern_grid`, weil der Inset selbst die Edge-Distance enkodiert.
Linear und Circular sind NICHT betroffen — sie nutzen edge_distances /
center_offset / anchor wie ein normales Single-Hole.

## Resolver-Mathe

100mm Wuerfel → face >Z: parent_w=parent_h=100, half=50, 50.

| ID | type | params | semantic | offset_x | offset_y | face |
|---|---|---|---|---|---|---|
| m01_grid_4_corners_centered | hole_pattern_grid | count=4, inset=10, hole_diameter=8, depth=5 | side=oben, centered | 0 | 0 | >Z |
| m02_grid_4_with_edge_distances_dropped | hole_pattern_grid | count=4, inset=10, hole_diameter=8, depth=5 | side=oben, edge_distances{top:5} (DROPPED) | 0 | 0 | >Z |
| m03_circular_centered | hole_pattern_circular | count=6, bolt_circle_diameter=60, hole_diameter=8, depth=5 | side=oben, centered | 0 | 0 | >Z |
| m04_circular_with_offset | hole_pattern_circular | count=4, bolt_circle_diameter=40, hole_diameter=6, depth=4 | center_offset{right:15, top:10} | +15 | +10 | >Z |
| m05_linear_with_anchor | hole_pattern_linear | count=5, spacing=15, start_offset=10, direction="x", hole_diameter=8, depth=5 | anchor parent=top_right, offset{down:10} | +50 | +40 | >Z |
| m06_grid_on_rechts_face | hole_pattern_grid | count=4, inset=10, hole_diameter=8, depth=5 | side=rechts, centered | 0 | 0 | >X |

## Detail-Mathe

### m02 (Grid mit edge_distances - bypass-Test)

`_resolve_feature` setzt `edge_distances=None` fuer `hole_pattern_grid`.
Folge: alignment=centered (Default), keine edge_distances/center_offset/
anchor → ox=0, oy=0. **Wenn der Bypass entfernt wird, wuerde der Test
sofort ROT** weil dann edge_distances{top:5} angewandt wuerde und
oy=+45 ergaebe statt 0.

### m05 (Linear mit Anchor)

hole_pattern_linear params: {hole_diameter, depth, count, spacing,
start_offset, direction}. Keine "x"/"y"/"diameter"-Keys. Daher
`_get_child_face_size`:
- cx = params.get("x") or params.get("diameter") or 0 = 0
- cy = same = 0
- is_face_local = "depth" in params and "z" not in params → True
- returns (0, 0)

child_anchor center on (0, 0): (0*0, 0*0) = (0, 0).
parent_anchor top_right on >Z (100, 100): (+50, +50).
ox = 50 - 0 = +50; oy = 50 - 0 = +50.
offset {down:10} → bottom 10 → wy-1*10 = -10.
oy = 50 + (-10) = +40.

Final: ox=+50, oy=+40, angle_deg=0.
