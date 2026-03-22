# Hole Simple — Bohrung mit definierter Tiefe
Tags: bohrung, loch, hole, bohren, sackloch, blind_hole

## Wann verwenden
- User sagt: "Bohrung", "Loch", "bohren" mit Tiefenangabe
- Sackloch (geht NICHT durch den ganzen Körper)

## CadQuery Code (modulare Funktion)

```python
def drill_hole(body: cq.Workplane, face_selector: str,
               diameter: float, depth: float,
               offset_x: float = 0, offset_y: float = 0) -> cq.Workplane:
    """Bohrt ein Sackloch in eine Fläche.

    Args:
        diameter: Durchmesser in mm (NICHT Radius)
        depth: Tiefe in mm
        offset_x: Versatz vom Face-Zentrum in X (mm)
        offset_y: Versatz vom Face-Zentrum in Y (mm)
    """
    return (body.faces(face_selector)
            .workplane(centerOption='CenterOfBoundBox')
            .center(offset_x, offset_y)
            .hole(diameter, depth))
```

## Parameter-Referenz
| Parameter | Typ | Beschreibung | Default |
|-----------|-----|--------------|---------|
| diameter | float | Bohrungsdurchmesser in mm | — |
| depth | float | Bohrungstiefe in mm (None = durchgehend) | None |

## Varianten
- `.hole(10, 15)`: ∅10mm, 15mm tief (Sackloch)
- `.hole(10)`: ∅10mm, durchgehend (= Durchgangsbohrung)
- `.circle(5).cutBlind(-15)`: Alternative — Kreis mit Radius 5 → cutBlind

## Häufige Fehler
1. **Durchmesser vs. Radius**: `.hole()` nimmt DURCHMESSER, `.circle()` nimmt RADIUS. User sagt "∅10mm" → `.hole(10)` ODER `.circle(5).cutBlind()`
2. **depth=None ist default**: Ohne Tiefenangabe wird die Bohrung durchgehend!
3. **Tiefe > Materialstärke**: Ergibt Durchgangsbohrung, nicht Sackloch

## Komposition
- Bohrung in Oberseite: `body.faces(">Z").workplane(cOBB).hole(d, depth)`
- Bohrung versetzt: `body.faces(">Z").workplane(cOBB).center(10, 20).hole(d)`
