# Structure Checklist — Code-Struktur prüfen
Tags: struktur, code, prüfung, funktionen, assemble

## Checkliste

1. ✓ `import cadquery as cq` vorhanden?
2. ✓ `from cadquery.selectors import NearestToPointSelector` wenn nötig?
3. ✓ `import math` wenn trigonometrische Funktionen verwendet?
4. ✓ `OUTPUT_PATH` definiert?
5. ✓ Parameter-Block am Anfang? (Konstanten statt Magic Numbers)
6. ✓ Eine Funktion pro Feature?
   → Nie 2 Features in einer Funktion
7. ✓ `make_base()` Funktion vorhanden? (gibt cq.Workplane zurück)
8. ✓ Jede Feature-Funktion: `def xxx(body: cq.Workplane) -> cq.Workplane:`?
9. ✓ `assemble()` Funktion vorhanden?
10. ✓ assemble() ruft alle Feature-Funktionen in korrekter Reihenfolge auf?
11. ✓ `result = assemble()` am Ende?
12. ✓ `cq.exporters.export(result, OUTPUT_PATH)` am Ende?
13. ✓ Jede Funktion hat Docstring?

## FAIL-Gründe (Code wird zurückgewiesen)
- Kein `assemble()` → FAIL
- Kein Export → FAIL
- Monolithischer Code ohne Funktionen → FAIL
- Magic Numbers statt Konstanten → WARNUNG (nicht FAIL)
