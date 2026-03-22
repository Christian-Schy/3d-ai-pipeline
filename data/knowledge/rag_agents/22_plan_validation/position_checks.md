# Position Checks — Feature innerhalb Parent-BBox?
Tags: position, prüfung, bounding_box, grenzen

## Checkliste

1. ✓ Placement hat face UND position?
2. ✓ Face-Selektor ist gültig? (">Z", "<Z", ">X", "<X", ">Y", "<Y", "NearestToPoint")
3. ✓ Position ist gültig? ("center", "flush_right", "corners", "offset", etc.)
4. ✓ Bei offset: offset_x und offset_y angegeben?
5. ✓ Feature bleibt innerhalb Parent-Grenzen?
   → |offset_x| + feature_x/2 ≤ parent_x/2
   → |offset_y| + feature_y/2 ≤ parent_y/2
6. ✓ Bei "flush_right": offset_x = parent_x/2 - feature_x/2?
7. ✓ Bei "corners" + inset: 4 Positionen alle innerhalb Parent?
8. ✓ Nach Union: selector_point angegeben wenn nötig?
9. ✓ selector_point Z-Wert = korrekte Top-Höhe des Parents?

## Fehler-Meldungen
- "FEHLER: Feature 'steg' mit offset_x=60 ragt über Parent (breite=100) hinaus"
- "FEHLER: placement hat kein face — wohin soll das Feature?"
- "WARNUNG: Feature nach Union ohne selector_point — Face-Selektion unsicher"
