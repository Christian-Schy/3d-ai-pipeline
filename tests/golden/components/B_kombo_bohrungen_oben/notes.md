# B_kombo — 6 Bohrungs-Variationen auf einem Wuerfel (oben-Face)

Stress-Test: alle 6 Bohrungs-Patterns gleichzeitig in einem Blueprint,
gleicher Parent-Wuerfel (200³), gleiches Bohrungs-Mass (d=18, depth=10).
Deckt B1 (Versatz aus Mitte), B2 (Abstand von Kanten), B3 (Mischung Achsen)
in einem Run ab.

User-Spec (Original mit Korrektur am Anfang):

> 200mm wuerfel, oben soll oben rechts jeweils von den kanten 10mm entfernt
> eine 18mm bohrung 10 tief hin, oben soll unten rechts eine 18mm bohrung
> jeweils von den kanten 10mm entfernt mit 10mm tiefe hin, oben soll nach
> links um 10mm und nach unten um 10mm versetzt eine 18mm bohrung hin 10
> tief, oben soll eine bohrung 18mm durchmesser 10 tief nach oben um 10mm
> versetzt und nach rechts um 10mm versetzt werden, oben soll von der
> oberen kante 10mm entfernt und nach links um 90mm versetzt eine 18mm
> bohrung hin mit 10 tiefe, oben soll von der unteren kante 10mm und von
> der linken seite 10mm entfernt eine 18mm bohrung hin mit 10 tiefe.

## Resolver-Mathe (verifiziert gegen src/tools/blueprint_resolver.py)

Wuerfel 200x200x200 → face=>Z, parent_w=parent_h=200, half=100.
Bohrung ist hole-like → is_box=False → child_half=0.

`_EDGE_AXIS_MAP[">Z"]`: right→(wx,+1), left→(wx,-1), top/back→(wy,+1),
bottom/front→(wy,-1).

`edge_distance: val_signed = sign * (half - val - child_half)` → 100-val
`center_offset: val_signed = sign * val`

| ID | Pattern | semantic | offset_x | offset_y |
|----|---------|----------|----------|----------|
| var1 | B2 oben-rechts | edge_distances{top:10, right:10}    | +90 | +90 |
| var2 | B2 unten-rechts | edge_distances{bottom:10, right:10} | +90 | -90 |
| var3 | B1 -/- versatz | center_offset{left:10, bottom:10}   | -10 | -10 |
| var4 | B1 +/+ versatz | center_offset{top:10, right:10}     | +10 | +10 |
| var5 | B3 mix Achsen | edge_distances{top:10} + center_offset{left:90} | -90 | +90 |
| var6 | B2 unten-links | edge_distances{bottom:10, left:10}  | -90 | -90 |

## Coverage

Phase 1 — Resolver only (deterministisch). Phase 2 (Pipeline-Goldens) ist
hier besonders wertvoll, weil der User in Real-Runs (8a170a03/dc21d2ab)
genau bei aehnlichen Mehr-Bohrungen-Specs Klassifizierer-Bugs gesehen hat
(falsche Seite + falsche Bohrungsposition). Layer 1 ist deterministisch
gruen — der echte Bug sitzt upstream im aktions_klassifizierer, nicht im
Resolver.
