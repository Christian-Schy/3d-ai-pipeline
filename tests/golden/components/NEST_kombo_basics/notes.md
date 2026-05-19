# NEST_kombo_basics — 6 Bohrung-in-Tasche Variationen

Stress-Test fuer den feature-in-feature Resolver-Pfad
`_resolve_feature_in_feature` in `src/tools/blueprint_resolver.py`. Wenn
`parent_id` auf eine subtraktive Tasche zeigt (`pocket_rect`, `slot`,
`groove`, `cutout`), berechnet der Resolver die Bohrungs-Offsets im
LOKAL-FRAME der Tasche (statt im Part-Face-Frame), rotiert sie um den
Pocket-Angle, und transformiert sie zurueck in den Part-Face-Frame.

**Plus Depth-Reference:** wenn der User keine eigene depth angibt
(default `depth_reference="auto"`), wird `child.depth + pocket.depth`
gerechnet → Bohrung schneidet vom Part-Top durch die Tasche und um
ihre eigene Tiefe IN den Tasche-Boden hinein.

## Setup

100mm Wuerfel + 4 Taschen (jede mit verschiedenem Placement) + 6
Bohrungen verteilt auf die Taschen.

| Tasche-ID | Tasche-Placement | Genutzt fuer |
|-----------|-------------------|--------------|
| nest_tasche_a_centered | oben centered, 60x40x10, ox=0, oy=0, angle=0 | n1, n2, n6 |
| nest_tasche_b_offset | oben center_offset{right:10}, ox=10, oy=0, angle=0 | n3 |
| nest_tasche_c_rotated30 | oben centered, angle=+30 | n4 |
| nest_tasche_d_rotated45 | oben centered, angle=+45 | n5 |

## Resolver-Mathe

Tasche-Frame fuer die Mathe: fake_parent_params = {x:60, y:40, z:10},
half_w=30, half_h=20. Bohrung ist hole-like → child_half=0.

| ID | Parent-Tasche | semantic | Local Math | Rotation | Final ox/oy/angle | depth |
|----|---------------|----------|------------|----------|---------------------|-------|
| n1_centered | a (centered) | side=oben, centered | 0, 0 | n/a | 0, 0, 0 | 5+10=15 |
| n2_kanten_top5_left8 | a (centered) | edge{top:5, left:8} | -22, +15 | n/a | -22, +15, 0 | 15 |
| n3_centered_in_offset_tasche | b (offset right=10) | side=oben, centered | 0, 0 | n/a | 0+10=10, 0, 0 | 15 |
| n4_centered_in_rotated_30 | c (angle=30) | side=oben, centered | 0, 0 | rotation of 0,0 = 0,0 | 0, 0, angle=30 | 15 |
| n5_versatz_in_rotated_45 | d (angle=45) | center_offset{right:5} | +5, 0 | rotation of (5,0) by 45 | 3.5355, 3.5355, angle=45 | 15 |
| n6_anchor_corner_in_tasche | a (centered) | edge{top:3, right:5} | +25, +17 | n/a | +25, +17, 0 | 15 |

## Detail-Mathe

### n2 (edge_distances within Tasche)
- top:5, wy+1, half=20, hole-like child_half=0: oy = +(20-5) = +15
- left:8, wx-1, half=30: ox = -(30-8) = -22
- pocket_angle=0 → rot stays (-22, +15)
- final_ox = parent_placement.offset_x (0) + (-22) = -22
- final_oy = parent_placement.offset_y (0) + 15 = +15

### n5 (versatz in rotated tasche — **kritischer Pfad**)
Lokal: center_offset{right:5} → local_ox=+5, local_oy=0.
Rotation um pocket_angle=+45° (CCW, math-positive):
- rot_ox = 5·cos(45°) - 0·sin(45°) = 5·0.7071 = 3.5355
- rot_oy = 5·sin(45°) + 0·cos(45°) = 5·0.7071 = 3.5355
- final_ox = 0 + 3.5355 = 3.5355
- final_oy = 0 + 3.5355 = 3.5355
- final_angle = (0 + 45) % 360 = 45

### n6 (edge_distances corner in Tasche)
- top:3, wy+1, half=20, hole-like child_half=0: oy = +(20-3) = +17
- right:5, wx+1, half=30: ox = +(30-5) = +25
- pocket_angle=0 → rot stays (+25, +17)
final_ox = 0 + 25 = +25; final_oy = 0 + 17 = +17.

## Depth-Reference

Alle Bohrungen haben `depth_reference="auto"` (Default). Da parent ein
Pocket ist, wird `pocket_floor` angewandt: `final_params.depth =
child.depth + pocket.depth`. Bohrung mit depth=5, Tasche mit depth=10
→ resolved depth=15. Plus `depth_local=5` (urspruengliche Bohrungs-
Tiefe als Audit).

Der Test prueft NUR den final depth=15. depth_local und
depth_reference_applied sind extra-Felder die das compare nicht ueberprueft.
