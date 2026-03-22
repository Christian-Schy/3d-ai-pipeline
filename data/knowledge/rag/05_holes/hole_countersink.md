# Countersink Hole — Kegelsenkung
Tags: kegelsenkung, countersink, senkkopf, senkkopfschraube, kegelbohrung, csk

## Wann verwenden
- User sagt: "Kegelsenkung", "Senkkopfschraube", "kegelförmige Senkung"
- Senkkopfschrauben bündig versenken (konisch, nicht zylindrisch)

## CadQuery Code (modulare Funktion)

```python
def drill_countersink(body: cq.Workplane, face_selector: str,
                       hole_diameter: float, csk_diameter: float,
                       csk_angle: float = 82.0, depth: float = None,
                       offset_x: float = 0, offset_y: float = 0) -> cq.Workplane:
    """Kegelsenk-Bohrung.

    Args:
        hole_diameter: Durchmesser der Bohrung (mm)
        csk_diameter: Durchmesser der Kegelsenkung an der Oberfläche (mm)
        csk_angle: Kegelwinkel in Grad (82° für metrische Schrauben, 90° USA)
        depth: Bohrungstiefe (None = durchgehend)
    """
    return (body.faces(face_selector)
            .workplane(centerOption='CenterOfBoundBox')
            .center(offset_x, offset_y)
            .cskHole(hole_diameter, csk_diameter, csk_angle, depth))
```

## Parameter-Referenz
| Parameter | Typ | Beschreibung | Default |
|-----------|-----|--------------|---------|
| diameter | float | Bohrungsdurchmesser (mm) | — |
| cskDiameter | float | Senkungsdurchmesser oben (mm) | — |
| cskAngle | float | Kegelwinkel in Grad | 82.0 |
| depth | float | Bohrungstiefe (None = durch) | None |

## Häufige Fehler
1. **Winkel**: 82° = Standard metrisch (DIN 963/965), 90° = US-Standard. Nicht verwechseln
2. **csk_diameter**: Das ist der Durchmesser an der OBERFLÄCHE, nicht die Tiefe der Senkung
3. **Reihenfolge**: `cskHole(hole_d, csk_d, csk_angle)` — hole zuerst
