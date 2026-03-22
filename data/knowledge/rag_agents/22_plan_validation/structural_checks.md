# Structural Checks — Feature Tree Struktur prüfen
Tags: struktur, prüfung, tree, validierung

## Checkliste (alle müssen PASS sein)

1. ✓ Hat das Tree mindestens ein Feature mit parent=null (Basis)?
2. ✓ Hat JEDES Feature eine eindeutige ID?
3. ✓ Hat JEDES Feature (außer Basis) einen gültigen Parent?
4. ✓ Existiert jeder referenzierte Parent in features?
5. ✓ Keine zirkulären Dependencies? (A→B→A verboten)
6. ✓ build_order enthält ALLE Feature-IDs?
7. ✓ build_order: Parent kommt VOR Child?
8. ✓ build_order: Basis ist ERSTER Eintrag?
9. ✓ Jedes Feature hat type aus dem Katalog?
10. ✓ Jedes Feature hat params mit nötigen Werten?

## Fehler-Meldungen (Beispiele)
- "FEHLER: Feature 'steg_bohrung' hat Parent 'steg' aber 'steg' existiert nicht"
- "FEHLER: build_order hat 'hole_1' vor Parent 'steg_rechts'"
- "FEHLER: Feature 'base' fehlt in build_order"
- "FEHLER: Zirkuläre Dependency: a → b → a"
