# Hole Angled — Bohrung unter Winkel
Tags: schrägbohrung, winkel, angled, schräg, geneigt, tilted

## Wann verwenden
- User sagt: "Bohrung unter 30°", "schräge Bohrung", "geneigte Bohrung"
- Bohrung die nicht senkrecht zur Fläche steht

## CadQuery Code (modulare Funktion)

```python
def drill_angled_hole(body: cq.Workplane, face_selector: str,
                       diameter: float, depth: float,
                       angle_x: float = 0, angle_y: float = 0,
                       offset_x: float = 0, offset_y: float = 0) -> cq.Workplane:
    """Bohrt ein Loch unter einem Winkel.

    Args:
        angle_x: Neigung um X-Achse in Grad
        angle_y: Neigung um Y-Achse in Grad
    """
    return (body.faces(face_selector)
            .workplane(centerOption='CenterOfBoundBox')
            .center(offset_x, offset_y)
            .transformed(rotate=(angle_x, angle_y, 0))
            .hole(diameter, depth))


def drill_angled_hole_cut(body: cq.Workplane, face_selector: str,
                           radius: float, depth: float,
                           angle_x: float = 0, angle_y: float = 0,
                           offset_x: float = 0, offset_y: float = 0) -> cq.Workplane:
    """Alternative: Schräge Bohrung via Zylinder + Cut."""
    cyl = (cq.Workplane("XY")
           .circle(radius)
           .extrude(depth)
           .rotate((0, 0, 0), (1, 0, 0), angle_x)
           .rotate((0, 0, 0), (0, 1, 0), angle_y)
           .translate((offset_x, offset_y, 0)))
    return body.cut(cyl).clean()
```

## Häufige Fehler
1. **transformed() Reihenfolge**: Erst `.center()` für Position, DANN `.transformed()` für Neigung
2. **Tiefe bei Schrägbohrung**: Die Tiefe folgt der geneigten Achse, nicht der Vertikalen
3. **Durchdringung**: Bei flachem Winkel kann die Bohrung seitlich herausragen → Geometrie vorher prüfen
4. **hole() vs. cut()**: `.hole()` mit `.transformed()` funktioniert, aber bei extremen Winkeln kann die cut()-Variante zuverlässiger sein
