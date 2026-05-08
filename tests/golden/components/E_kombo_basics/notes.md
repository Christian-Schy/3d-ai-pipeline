# E_kombo_basics — 12 Extrusion-Platten-Variationen auf 100mm Wuerfel

Stress-Test fuer Multi-Part-Anchor + Plate-Orientation. Hier liegen die
meisten Real-Run-Bugs der letzten Wochen (Bug 7+8, ADR 0004).

Jede Variation ist eine eigene Platte (parent=wuerfel) mit verschiedener
Anchor-/Orientation-Kombination. Plates ueberlappen geometrisch — fuer
den Resolver irrelevant.

## Konventionen

- Plate raw params (vor orientation): {x:80, y:40, z:20}.
- orientation `80x40_liegt_auf` resolved je nach side:
  - vorne (<Y): contact=X×Z, depth=Y → x=80, y=20, z=40
  - oben  (>Z): contact=X×Y, depth=Z → x=80, y=40, z=20
  - rechts (>X): contact=Y×Z, depth=X → x=20, y=80, z=40
- Wuerfel-Face dims auf <Y/>Z/>X jeweils (100, 100).
- Anchor-Konvention: `_FACE_VIEWER_H_FLIP = {<X, >Y}`. <Y, >Z, >X NICHT
  geflippt — Anchor-Keywords mappen direkt.

## Resolver-Mathe

| ID | side | resolved params | child_face_dims | Anchor / Math | offset_x | offset_y | angle_deg |
|---|---|---|---|---|---|---|---|
| e01_vorne_centered | vorne | x=80,y=20,z=40 | (80, 40) | alignment centered | 0 | 0 | 0 |
| e02_vorne_corner_top_right | vorne | (80, 40) | child=top_right, parent=top_right; (50-40, 50-20) | +10 | +30 | 0 |
| e03_vorne_corner_with_left_offset | vorne | (80, 40) | E2 + offset{left:10}; (10-10, 30) | 0 | +30 | 0 |
| e04_vorne_edge_bottom_anchor | vorne | (80, 40) | child=bottom_edge, parent=bottom_edge; (0, -50-(-20)) | 0 | -30 | 0 |
| e05_vorne_corner_with_rotation_ccw | vorne | (80, 40) | E2 + angle=+20 (siehe Detail-Mathe) | +19.2527 | +17.5253 | +20 |
| e06_vorne_corner_bottom_left | vorne | (80, 40) | child=bottom_left, parent=bottom_left; (-50-(-40), -50-(-20)) | -10 | -30 | 0 |
| e07_vorne_edge_top_with_down_offset | vorne | (80, 40) | child=top_edge, parent=top_edge, offset{down:5}; (0, 50-20-5) | 0 | +25 | 0 |
| e08_oben_plate_centered | oben | x=80,y=40,z=20 | (80, 40) | alignment centered | 0 | 0 | 0 |
| e09_oben_plate_corner_to_corner | oben | (80, 40) | child=top_right, parent=top_right | +10 | +30 | 0 |
| e10_rechts_plate_centered | rechts | x=20,y=80,z=40 | (80, 40) | alignment centered | 0 | 0 | 0 |
| e11_vorne_centered_cw_rotation | vorne | (80, 40) | alignment centered, angle=-20 (CW) | 0 | 0 | -20 |
| e12_vorne_corner_to_edge_with_up_offset | vorne | (80, 40) | child=bottom_right, parent=bottom_edge, offset{up:10} | -40 | -20 | 0 |

## Detail-Mathe

### e05 (Pre-Rotation +20° CCW)

Per `_apply_anchor:840-846`: child_anchor wird VOR dem Subtrahieren
rotiert (damit die Ecke nach Rotation am Parent-Punkt haengen bleibt).

- child_raw top_right = (+40, +20)
- rotation +20°:
  - new_x = 40·cos(20°) - 20·sin(20°) = 37.5878 - 6.8404 = 30.7474
  - new_y = 40·sin(20°) + 20·cos(20°) = 13.6808 + 18.7939 = 32.4747
- ox = 50 - 30.7474 = 19.2526 → round 19.2527
- oy = 50 - 32.4747 = 17.5253

(Mehr Praezision: cos(20°)=0.9396926..., sin(20°)=0.3420201...
new_x = 30.747302..., new_y = 32.474658...
ox = 19.252698..., oy = 17.525342... → round to 4: 19.2527, 17.5253.)

### e12 (corner-to-edge mit Offset)

- parent_anchor bottom_edge auf <Y: (0, -0.5)*(100, 100) = (0, -50)
- child_anchor bottom_right von (80, 40): (+0.5*80, -0.5*40) = (+40, -20)
- ox = 0 - 40 = -40
- oy = -50 - (-20) = -30
- offset {up:10} → top wy+1*10 = +10
- ox = -40, oy = -30 + 10 = -20
