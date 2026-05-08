# B_kombo_asymmetric_multiface — Asymmetrischer Wuerfel, Bohrungen auf 2 Faces

Stress-Test fuer Achsen-Mapping pro Face. Asymmetrischer Wuerfel
(200x100x80) macht sofort sichtbar wenn der Resolver parent_w/parent_h
verwechselt — bei symmetrischen Wuerfeln faellt das nicht auf.

User-Spec (Stilvariante mit explizitem Wechsel zwischen oben + rechts):

> 200x100x80 wuerfel; oben (also auf der 200x100 flaeche): oben rechts
> jeweils von kanten 10mm entfernt eine 18mm bohrung 10 tief; unten links
> jeweils von kanten 10mm entfernt eine 18mm bohrung 10 tief; nach oben
> 20mm und nach rechts 30mm versetzt eine 18mm bohrung 10 tief; rechts
> (also auf der 100x80 flaeche): oben rechts jeweils von kanten 10mm
> entfernt eine 12mm bohrung 8 tief; nach unten 15mm und nach links 20mm
> versetzt eine 12mm bohrung 8 tief; von oberer kante 5mm entfernt und
> nach links um 20mm versetzt eine 12mm bohrung 8 tief.

## Resolver-Mathe

`_get_face_dimensions` mappt:
- `>Z`: parent_w = x = 200, parent_h = y = 100 → halves 100, 50
- `>X`: parent_w = y = 100, parent_h = z = 80  → halves 50, 40

Bohrung ist hole-like → child_half=0.

| ID | Face | semantic | Mathe | offset_x | offset_y |
|----|------|----------|-------|----------|----------|
| asym_z_top_right_kanten | >Z | edge_distances{top:10, right:10} | +(100-10), +(50-10) | +90 | +40 |
| asym_z_unten_links_kanten | >Z | edge_distances{bottom:10, left:10} | -(100-10), -(50-10) | -90 | -40 |
| asym_z_versatz_oben_rechts | >Z | center_offset{top:20, right:30} | +30, +20 | +30 | +20 |
| asym_x_top_right_kanten | >X | edge_distances{top:10, right:10} | +(50-10), +(40-10) | +40 | +30 |
| asym_x_versatz_unten_links | >X | center_offset{bottom:15, left:20} | -20, -15 | -20 | -15 |
| asym_x_mix_axes | >X | edge_distances{top:5} + center_offset{left:20} | center auf X (kein edge), edge auf Y | -20 | +35 |

`asym_x_mix_axes`: edge_distances{top:5} setzt nur Y-Achse (oy_edge_set);
center_offset{left:20} setzt nur X-Achse (ox_center_set). Da kein edge
auf X gesetzt, promoviert center via elif-chain in
`_compute_offsets:995-1015`. Kein additives Mischen (Bug-4-Pfad), weil
die zwei Quellen auf verschiedenen Achsen sind.
