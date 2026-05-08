# B_kombo_additive_anchor — Additive Achsen-Mischung + Anchor-Corner mit Versatz

Stress-Test fuer zwei Code-Pfade die der einfache B_kombo_oben nicht
abdeckt:
1. **Additive Bug-4-Pfad** (`_compute_offsets:1009-1015`): edge_distance
   UND center_offset auf DERSELBEN Achse → edge ist Basis, center ist
   additiv. Beispiel-User-Phrasing: "20mm von rechter Kante, zusaetzlich
   10mm nach rechts versetzt".
2. **Anchor mit Corner-Versatz** (`_apply_anchor:806-868`): Kindpunkt auf
   Eltern-Ecke, plus zusaetzlicher Versatz-Vektor. Beispiel-User-Phrasing:
   "obere rechte Ecke der oberen Flaeche, 20mm nach unten und 30mm nach
   links versetzt".

User-Spec:

> 200mm wuerfel; oben: 20mm von rechter kante und zusaetzlich 10mm nach
> rechts versetzt eine 18mm bohrung 10 tief; oben: 30mm von linker kante
> und zusaetzlich 5mm nach rechts versetzt eine 18mm bohrung 10 tief;
> oben: 25mm von oberer kante und zusaetzlich 5mm nach unten versetzt
> eine 18mm bohrung 10 tief; oben: obere rechte ecke der oberseite,
> 20mm nach unten und 30mm nach links versetzt eine 18mm bohrung 10 tief;
> oben: untere linke ecke der oberseite, 25mm nach oben und 15mm nach
> rechts versetzt eine 18mm bohrung 10 tief.

## Resolver-Mathe

Wuerfel 200³ → face=>Z, parent_w=parent_h=200, half=100.

### Additive (3 Bohrungen)

`_compute_offsets`: edge ist Basis (priority 2b), center wird ADDIERT
(`if ox_center_set and (ox_pocket_set or ox_edge_set): ox += ox_from_center`).

| ID | semantic | Mathe | offset_x | offset_y |
|----|----------|-------|----------|----------|
| add_right_edge_plus_versatz | edge{right:20} + center{right:10} | +(100-20) + 10 | +90 | 0 |
| add_left_edge_plus_versatz | edge{left:30} + center{right:5} | -(100-30) + 5 | -65 | 0 |
| add_top_edge_plus_versatz_y | edge{top:25} + center{bottom:5} | +(100-25) + (-5) | 0 | +70 |

### Anchor mit Offset (2 Bohrungen)

`_apply_anchor`: parent_anchor_point - child_anchor_point + offset
(child_point default=center → child_wx=child_wy=0).

| ID | parent_point | offset | Mathe | offset_x | offset_y |
|----|--------------|--------|-------|----------|----------|
| anchor_top_right_corner_offset | top_right (+0.5,+0.5)·200 | {down:20, left:30} → bottom 20, left 30 | (100-30, 100-20) | +70 | +80 |
| anchor_bottom_left_corner_offset | bottom_left (-0.5,-0.5)·200 | {up:25, right:15} → top 25, right 15 | (-100+15, -100+25) | -85 | -75 |

`_ANCHOR_OFFSET_ALIAS` mappt down→bottom, up→top, dann
`_apply_center_offset` mit den Aliases. Anchor ueberschreibt edge +
center komplett (`_compute_offsets:909`).

## Coverage

- Bug-4-Pfad (additiv same-axis): 3 Bohrungen in verschiedenen
  Vorzeichen-Kombinationen (+/+, -/+, +/-)
- Anchor-Corner-Offset: 2 Ecken in entgegengesetzten Quadranten

Die anderen anchor-Patterns (anchor an Kanten-Mittelpunkt, anchor mit
pre_rotation) sind hier nicht abgedeckt — separate Goldens wenn der
User sie als Test-Case spezifiziert.
