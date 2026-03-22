# Completeness Checks — Ist alles aus der Beschreibung enthalten?
Tags: vollständigkeit, komplett, prüfung, fehlt

## Checkliste

1. ✓ Alle genannten Grundkörper vorhanden?
   → User sagt "Platte" → base_plate existiert?
2. ✓ Alle genannten Features vorhanden?
   → User sagt "Steg" → extrusion_rect existiert?
   → User sagt "Bohrung" → hole_single existiert?
   → User sagt "Lochkreis" → hole_pattern_circular existiert?
3. ✓ Alle genannten Maße eingetragen?
   → User sagt "100x80x20" → params hat x=100, y=80, z=20?
   → User sagt "∅10" → diameter=10?
4. ✓ Alle Positionen zugeordnet?
   → User sagt "rechts" → placement hat flush_right oder offset_x>0?
   → User sagt "darin" → Parent korrekt gesetzt?
5. ✓ Anzahl stimmt?
   → User sagt "6 Löcher" → n_holes=6?
   → User sagt "4 Eckbohrungen" → count=4?
6. ✓ Tiefe korrekt interpretiert?
   → User sagt "durchgehend" → depth=null?
   → User sagt "10mm tief" → depth=10?

## Fehler-Meldungen
- "FEHLER: User nennt 'Lochkreis' aber kein hole_pattern_circular im Tree"
- "FEHLER: User sagt '∅10mm' aber diameter=20 im Feature"
- "WARNUNG: User nennt keine Tiefe für Bohrung — als durchgehend interpretiert"
