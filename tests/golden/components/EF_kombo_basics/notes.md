# EF_kombo_basics — 10 Feature-Variationen auf einer Platte

Stress-Test fuer Features-auf-Extrusion-Pfad (parent=plate statt parent=cube).

**Plate-Setup** (vereinfacht, kein orientation-swap):
- 100mm Wuerfel + Platte 60x40x10 oben centered, orientation=standard.
- Plate-Placement: face=>Z, ox=0, oy=0, parent_swap="none".
- Plate-Frame fuer EF: parent_w=60, parent_h=40, halves 30, 20.

EF-Features haben parent=plate. Resolver berechnet Offsets relativ zum
Plate-Center (NICHT relativ zum Wuerfel) — Plate-Placement wird im
Assembler durch das Plate-Coord-System wegtransformiert.

## Konventionen

- Plate raw params {x:60, y:40, z:10}, orientation="standard" — keine
  Dimension-Umordnung, parent_swap="none".
- EF parent_w/h kommen aus Plate-Params: auf >Z Plate-Face = (60, 40).
- Bohrung ist hole-like → child_half=0 fuer edge_distances default.
- Anchor mit hole_single: `_get_child_face_size` returnt
  (diameter, diameter), also nicht (0, 0). Fuer ef06/ef07 ergibt das
  child_anchor != (0, 0).
- Pocket auf Plate ist hole-like → wie auf Wuerfel.
- pocket_edge_distances forciert is_box=True → child_half_w/h subtracted.

## Resolver-Mathe

| ID | type | params | semantic | Math | offset_x | offset_y | face | angle_deg |
|---|---|---|---|---|---|---|---|---|
| ef01_bohrung_default_centered | hole_single | d=5, depth=5 | side=oben, centered | 0, 0 | 0 | 0 | >Z | 0 |
| ef02_bohrung_kanten_top10_left8 | hole_single | d=5, depth=5 | edge{top:10, left:8} | hole-like child_half=0; +(20-10), -(30-8) | -22 | +10 | >Z | 0 |
| ef03_bohrung_other_face_unten | hole_single | d=5, depth=5 | side=unten, centered | 0, 0 | 0 | 0 | <Z | 0 |
| ef04_bohrung_anchor_corner_offset | hole_single | d=5, depth=5 | anchor top_right + offset{down:5, left:8} | (30, 20) + (-8, -5) | +22 | +15 | >Z | 0 |
| ef05_bohrung_versatz_aus_mitte | hole_single | d=6, depth=4 | center{right:10, top:5} | +10, +5 | +10 | +5 | >Z | 0 |
| ef06_bohrung_anchor_corner_to_corner | hole_single | d=5, depth=5 | child=top_right, parent=top_right (mit child face dim 5x5) | (30-2.5, 20-2.5) | +27.5 | +17.5 | >Z | 0 |
| ef07_bohrung_anchor_edge_to_edge | hole_single | d=5, depth=5 | child=right_edge, parent=right_edge | (30-2.5, 0-0) | +27.5 | 0 | >Z | 0 |
| ef08_tasche_pocket_edge_on_plate | pocket_rect | x=30, y=20, depth=5 | pocket_edge{right:5, bottom:3} | child_halves 15,10; +(30-5-15), -(20-3-10) | +10 | -7 | >Z | 0 |
| ef09_tasche_rotated_on_plate | pocket_rect | x=30, y=20, depth=5 | centered, angle=+30 | 0, 0, angle=+30 | 0 | 0 | >Z | +30 |
| ef10_nut_on_plate | slot | length=30, width=5, depth=3 | center_offset{right:8}, angle=0 | +8, 0 | +8 | 0 | >Z | 0 |

## Coverage

- Bohrung: default-centered, edge_distances, andere Face, anchor+offset,
  center_offset, anchor corner-to-corner (mit hole-Face-Dim), anchor
  edge-to-edge
- Tasche auf Platte: pocket_edge_distances (edge-to-edge), Rotation
- Nut auf Platte: center_offset + Achse

NICHT abgedeckt (separate Combo wenn gewuenscht):
- EF auf re-orientierter Platte (parent_swap-Pfad — bekannte
  Resolver-Limitierung mit AxB_liegt_auf parents)
- Mehrere Features auf einer Platte mit Verschachtelung
