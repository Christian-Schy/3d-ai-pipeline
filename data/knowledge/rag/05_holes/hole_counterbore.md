# Counterbore Hole — Stufenbohrung / Senkbohrung (zylindrisch)
Tags: stufenbohrung, senkbohrung, counterbore, cbore, zylindersenkung, innensechskant, schraubenkopf

## Wann verwenden
- User sagt: "Stufenbohrung", "Senkbohrung", "Innensechskantschraube versenken"
- Schraube soll bündig oder versenkt sitzen (zylindrische Senkung)

## CadQuery Code (modulare Funktion)

```python
def drill_counterbore(body: cq.Workplane, face_selector: str,
                       hole_diameter: float, cbore_diameter: float,
                       cbore_depth: float, depth: float = None,
                       offset_x: float = 0, offset_y: float = 0) -> cq.Workplane:
    """Stufenbohrung mit zylindrischer Senkung.

    Args:
        hole_diameter: Durchmesser der Durchgangsbohrung (mm)
        cbore_diameter: Durchmesser der Senkung (mm)
        cbore_depth: Tiefe der Senkung (mm)
        depth: Tiefe der Bohrung (None = durchgehend)
    """
    return (body.faces(face_selector)
            .workplane(centerOption='CenterOfBoundBox')
            .center(offset_x, offset_y)
            .cboreHole(hole_diameter, cbore_diameter, cbore_depth, depth))
```

## Parameter-Referenz
| Parameter | Typ | Beschreibung | Default |
|-----------|-----|--------------|---------|
| diameter | float | Bohrungsdurchmesser (mm) | — |
| cboreDiameter | float | Senkungsdurchmesser (mm) | — |
| cboreDepth | float | Senkungstiefe (mm) | — |
| depth | float | Bohrungstiefe (None = durch) | None |

## Häufige Fehler
1. **Reihenfolge der Parameter**: `cboreHole(hole_d, cbore_d, cbore_depth)` — Bohrung zuerst, Senkung danach
2. **cbore_diameter < hole_diameter**: Senkung MUSS größer als Bohrung sein
3. **cbore_depth > Materialstärke**: Senkung tiefer als Material → ungültiger Körper
