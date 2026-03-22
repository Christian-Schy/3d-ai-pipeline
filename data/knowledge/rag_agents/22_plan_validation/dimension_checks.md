# Dimension Checks — Maße plausibel?
Tags: dimension, maße, prüfung, plausibilität

## Checkliste

1. ✓ Alle Maße > 0? (keine negativen/null Dimensionen)
2. ✓ Basis-Maße vorhanden? (x, y, z alle definiert)
3. ✓ Bohrung-Durchmesser < Parent-Kleinstmaß?
   → hole_d < min(parent_x, parent_y)
4. ✓ Bohrung-Tiefe ≤ Parent-Höhe? (wenn depth angegeben)
5. ✓ Tasche-Tiefe < Parent-Höhe? (Boden muss übrig bleiben)
6. ✓ Feature kleiner als Parent?
   → feature_x ≤ parent_x UND feature_y ≤ parent_y
7. ✓ Lochkreis passt auf Parent?
   → circle_d/2 + hole_d/2 < min(parent_x, parent_y)/2
8. ✓ Eckbohrungen: inset > hole_d/2?
9. ✓ Wandstärke bei Bohrung in Feature ≥ 2mm?
   → (feature_breite - hole_d) / 2 ≥ 2
10. ✓ Fillet-Radius < kürzeste Kante?

## Fehler-Meldungen
- "FEHLER: hole_d=20 > parent_breite=15 — Bohrung passt nicht"
- "WARNUNG: Wandstärke nur 1mm bei Bohrung ∅8 in Steg ∅10"
- "FEHLER: Lochkreis ragt über Parent-Rand hinaus"
