# T_kombo_basics — 14 Tasche-Variationen auf 100mm Wuerfel

Stress-Test fuer Pocket-Resolver-Mathe. Deckt T1-T4 (ADR 0005) plus
edge-zu-edge in beiden Quadranten, Mischung der Edge-Distance-Modi mit
Center-Offset, Anchor-Patterns (corner+offset, corner-to-corner,
corner-to-edge), Rotations-Faelle und andere Face.

User-Spec (Phase T.1, ohne Bohrungen-in-Tasche — die kommen spaeter
unter NEST):

> 100mm wuerfel, oben eine tasche 60x40x10 10mm nach rechts versetzt
> zentral, oben eine tasche 60x40x10 von oben 20mm und von links 30mm
> entfernt, oben eine tasche 60x40x10 zentral 20 grad gegen uhrzeigersinn
> gedreht, oben eine tasche 30x20x10 deren rechte kante 25mm von rechter
> wuerfelkante und untere kante 10mm von unterer wuerfelkante entfernt,
> oben eine tasche 30x20x10 deren obere kante 15mm von oberer wuerfelkante
> und linke kante 20mm von linker wuerfelkante entfernt, oben eine tasche
> 30x20x10 von rechter kante 30mm und 5mm aus mitte nach unten, oben eine
> tasche 30x20x10 deren rechte kante 25mm von rechter wuerfelkante und
> 10mm aus mitte nach oben, oben eine tasche 30x20x10 obere rechte ecke
> 10mm nach unten und 20mm nach links versetzt, oben eine tasche 30x20x10
> obere rechte ecke der tasche auf obere rechte ecke des wuerfels, oben
> eine tasche 30x20x10 obere rechte ecke der tasche liegt auf rechter
> kante des wuerfels 5mm nach unten versetzt, rechts eine tasche 40x30x8
> mittig, oben eine tasche 50x30x10 10mm nach rechts versetzt 25 grad im
> uhrzeigersinn gedreht, oben eine tasche 50x30x10 von oben 30mm und von
> rechts 25mm entfernt 15 grad gegen uhrzeigersinn gedreht, oben eine
> tasche 30x20x10 obere rechte ecke der tasche auf obere rechte ecke des
> wuerfels 30 grad gegen uhrzeigersinn gedreht.

## Konventionen

- params: {x, y, depth} — x = horizontale Face-Ausdehnung,
  y = vertikale Face-Ausdehnung (Viewer-Sicht), depth = in die Face hinein.
- pocket_rect ist hole-like → `is_hole_like=True` in `_compute_offsets`,
  daher `is_box=False` fuer `edge_distances` (DEFAULT edge-zu-CENTER).
- Fuer EXPLIZITES edge-zu-EDGE: separates Schema-Feld
  `position.pocket_edge_distances` (forciert `is_box=True`, child_half
  wird abgezogen).
- Rotation: per Klassifizierer-Konvention — CCW (gegen Uhrzeigersinn) =
  positiv, CW (im Uhrzeigersinn) = negativ.
- Anchor mit Rotation: child_anchor wird VOR der Subtraktion rotiert
  (`_apply_anchor:840-846`), damit Ecke nach Rotation am Parent-Punkt
  haengen bleibt.

## Coverage-Matrix

| Pattern | Variationen |
|---------|-------------|
| center_offset | t01, t06, t07 (mix), t12 (mit Rotation) |
| edge_distances (hole-like default) | t02, t06 (mix), t13 (mit Rotation) |
| pocket_edge_distances (edge-zu-edge) | t04, t05, t07 (mix) |
| Mischung Achsen | t06, t07 (verschiedene Edge-Modi) |
| anchor parent_point=corner | t08, t09, t14 |
| anchor parent_point=edge | t10 |
| anchor child_point=corner | t09, t10, t14 |
| anchor mit Offset | t08, t10 |
| Rotation centered | t03 |
| Rotation + center_offset | t12 |
| Rotation + edge_distances | t13 |
| Rotation + anchor (pre-rotation) | t14 |
| Andere Face (>X) | t11 |
| Beide CCW + CW Rotation | t03, t12, t13, t14 (CCW=+); t12 (CW=-) |

## Detail-Mathe

100mm Wuerfel → face >Z: parent_w=parent_h=100, half=50,50.
Face >X: parent_w=100 (y), parent_h=100 (z), half=50,50.

### t04 (pocket_edge_distances right+bottom)
- pocket size 30x20: child_half_w=15, child_half_h=10
- right:25, wx+1: ox = +(50-25-15) = +10
- bottom:10, wy-1: oy = -(50-10-10) = -30

### t05 (pocket_edge_distances top+left)
- pocket size 30x20: child_half_w=15, child_half_h=10
- top:15, wy+1: oy = +(50-15-10) = +25
- left:20, wx-1: ox = -(50-20-15) = -15

### t06 (Mix edge_distances + center_offset, default hole-like)
- right:30, wx+1, child_half=0 (hole-like): ox_edge = +(50-30) = +20
- bottom:5, wy-1: oy_center = -5
- ox_edge_set → ox=+20; oy_center_set (no edge) → oy=-5

### t07 (Mix pocket_edge + center_offset)
- pocket_edge_right:25, wx+1, child_half_w=15: ox_pocket = +(50-25-15) = +10
- top:10, wy+1: oy_center = +10
- ox_pocket_set → ox=+10; oy_center_set (no edge) → oy=+10

### t08 (Anchor corner + offset)
- parent_anchor top_right on >Z: (+0.5, +0.5) * (100, 100) = (+50, +50)
- child_anchor center: (0, 0)
- ox = 50 - 0 = +50; oy = 50 - 0 = +50
- offset {down:10, left:20} → bottom 10, left 20
- _apply_center_offset >Z: bottom wy-1 → -10; left wx-1 → -20
- ox = 50 + (-20) = +30; oy = 50 + (-10) = +40

### t09 (Anchor corner-to-corner)
- parent_anchor top_right: (+50, +50)
- child_anchor top_right: (+0.5*30, +0.5*20) = (+15, +10)
- ox = 50 - 15 = +35; oy = 50 - 10 = +40

### t10 (Anchor child-corner-on-parent-edge + offset)
- parent_anchor right_edge on >Z: (+0.5, 0) * (100, 100) = (+50, 0)
- child_anchor top_right: (+15, +10)
- ox = 50 - 15 = +35; oy = 0 - 10 = -10
- offset {down:5} → bottom 5 → wy-1 → -5
- ox = +35; oy = -10 + (-5) = -15

### t14 (Anchor corner-to-corner WITH rotation +30°)
- parent_anchor top_right: (+50, +50)
- child_anchor raw top_right: (+15, +10)
- pre-rotation by +30° (CCW):
  - new_x = 15*cos(30°) - 10*sin(30°) = 12.99038 - 5.0 = 7.99038
  - new_y = 15*sin(30°) + 10*cos(30°) = 7.5 + 8.66025 = 16.16025
- ox = 50 - 7.99038 = 42.00962 → round 42.0096
- oy = 50 - 16.16025 = 33.83975 → round 33.8397
