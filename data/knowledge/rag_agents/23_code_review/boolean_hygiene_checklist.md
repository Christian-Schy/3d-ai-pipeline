# Boolean Hygiene — .clean(), Reihenfolge, Face-Selektoren
Tags: boolean, hygiene, clean, reihenfolge, face_selektor

## Checkliste

### .clean() Prüfung
1. ✓ Nach JEDER .union() → .clean() vorhanden?
2. ✓ Nach JEDER .cut() → .clean() vorhanden?
3. ✓ Kein doppeltes .clean().clean()?
4. ✓ .clean() NICHT nach .hole() (unnötig, hole macht intern clean)?

### Reihenfolge Prüfung
5. ✓ Basis-Bohrungen VOR erster Union?
6. ✓ Feature-Bohrungen NACH der Union des Features?
7. ✓ Fillet/Chamfer NACH allen Booleans?
8. ✓ Keine Union NACH Fillet?

### Face-Selektor Prüfung
9. ✓ Nach Union: NearestToPointSelector statt >Z?
10. ✓ Vor Union: einfache Selektoren (>Z etc.) sind OK?
11. ✓ centerOption='CenterOfBoundBox' bei jedem .workplane()?
12. ✓ NearestToPointSelector Punkt liegt auf der richtigen Face?

### Variable-Flow
13. ✓ result = make_base() → result wird weiterverwendet?
14. ✓ result = add_xxx(result) → Zuweisung nicht vergessen?
15. ✓ assemble() gibt result zurück?

## Schweregrade
- .clean() fehlt → FEHLER
- Reihenfolge falsch → FEHLER
- >Z nach Union → WARNUNG (kann funktionieren wenn Feature das höchste ist)
- centerOption fehlt → WARNUNG
- Variable nicht zugewiesen → FEHLER
