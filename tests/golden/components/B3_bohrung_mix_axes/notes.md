# B3 — Bohrung Mischung Achsen (edge_distance + center_offset)

**Spec-Variation 1 (User-Original):** "200mm wuerfel, oben soll von der oberen
kante 10mm entfernt und nach links um 90mm versetzt eine 18mm bohrung hin
mit 10 tiefe"

**Spec-Variation 2:** "200mm wuerfel, oben eine 18mm bohrung 10mm von oberer
kante, 90mm aus mitte nach links, 10 tief"

**Spec-Variation 3 (Feature-Matrix-Beispiel):** "oben eine bohrung 10mm von
links, 5mm aus mitte nach unten, d10 5 tief" (kleinerer Wuerfel-Fall, hier
nicht abgebildet — als Pattern dokumentiert)

## Resolver-Mathe

Wuerfel 200³ → face=>Z, parent_w=parent_h=200, half=100. Bohrung d=18,
hole-like → child_half=0.

`edge_distances={top:10}` → wy=+1, oy_edge_set:
  oy = +1 * (100 - 10) = +90

`center_offset={left:90}` → wx=-1, ox_center_set:
  ox = -1 * 90 = -90

Auf X-Achse: keine edge_distance gesetzt → center_offset promoviert via
elif-chain (`_compute_offsets:995-1015`) → ox=-90.
Auf Y-Achse: edge_distance gesetzt, kein center_offset → oy=+90.

Kein additives Mischen auf derselben Achse (das wuerde der Bug-4-Pfad
machen — siehe `blueprint_resolver.py:986-1015`). Hier sind die zwei
Quellen auf VERSCHIEDENEN Achsen.

→ `placement.offset_x=-90, offset_y=+90, face=">Z"`

## Coverage

Pattern: edge_distance auf einer Achse + center_offset auf der anderen
Achse. Wichtigster Test, weil der Resolver-Code zwei separate Quellen
korrekt zu einer Position kombinieren muss.
