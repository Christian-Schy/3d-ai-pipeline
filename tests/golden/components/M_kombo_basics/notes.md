# M_kombo_basics — 5 Pattern-Variationen auf 100mm Wuerfel

Stress-Test fuer Lochmuster-Resolver-Pfad. Zwei Pattern-Typen:
- hole_pattern_grid: NxM Raster (.rarray)
- hole_pattern_circular: Lochkreis (.polarArray)

**Kritischer Code-Pfad: Grid-Bypass.** `_resolve_feature:1212-1216`
forciert edge_distances/pocket_edge_distances auf None fuer
`hole_pattern_grid`, weil der Inset selbst die Edge-Distance enkodiert.
Circular ist NICHT betroffen — es nutzt center_offset wie ein normales
Single-Hole.

## Resolver-Mathe

100mm Wuerfel → face >Z: parent_w=parent_h=100, half=50, 50.

| ID | type | params | semantic | offset_x | offset_y | face |
|---|---|---|---|---|---|---|
| m01_grid_4_corners_centered | hole_pattern_grid | count=4, inset=10, hole_diameter=8, depth=5 | side=oben, centered | 0 | 0 | >Z |
| m02_grid_4_with_edge_distances_dropped | hole_pattern_grid | count=4, inset=10, hole_diameter=8, depth=5 | side=oben, edge_distances{top:5} (DROPPED) | 0 | 0 | >Z |
| m03_circular_centered | hole_pattern_circular | count=6, bolt_circle_diameter=60, hole_diameter=8, depth=5 | side=oben, centered | 0 | 0 | >Z |
| m04_circular_with_offset | hole_pattern_circular | count=4, bolt_circle_diameter=40, hole_diameter=6, depth=4 | center_offset{right:15, top:10} | +15 | +10 | >Z |
| m06_grid_on_rechts_face | hole_pattern_grid | count=4, inset=10, hole_diameter=8, depth=5 | side=rechts, centered | 0 | 0 | >X |

## Detail-Mathe

### m02 (Grid mit edge_distances - bypass-Test)

`_resolve_feature` setzt `edge_distances=None` fuer `hole_pattern_grid`.
Folge: alignment=centered (Default), keine edge_distances/center_offset/
anchor → ox=0, oy=0. **Wenn der Bypass entfernt wird, wuerde der Test
sofort ROT** weil dann edge_distances{top:5} angewandt wuerde und
oy=+45 ergaebe statt 0.
