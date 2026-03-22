# Hole on Side Face — Bohrung auf Seitenfläche
Tags: seitenbohrung, seitlich, querbohrung, horizontal, side_hole, seitenfläche

## Wann verwenden
- User sagt: "Bohrung von der Seite", "seitliche Bohrung", "Querbohrung"
- Bohrung nicht von oben/unten sondern von einer Seitenfläche

## CadQuery Code (modulare Funktion)

```python
def drill_side_hole(body: cq.Workplane, face_selector: str,
                     diameter: float, depth: float = None,
                     offset_x: float = 0, offset_y: float = 0) -> cq.Workplane:
    """Bohrt ein Loch auf einer Seitenfläche.

    Args:
        face_selector: z.B. ">X" (rechte Seite), "<X" (links), ">Y", "<Y"
        offset_x: Versatz horizontal auf der Face
        offset_y: Versatz vertikal auf der Face
    """
    wp = (body.faces(face_selector)
          .workplane(centerOption='CenterOfBoundBox')
          .center(offset_x, offset_y))

    if depth is not None:
        return wp.hole(diameter, depth)
    return wp.hole(diameter)


def drill_hole_from_right(body: cq.Workplane, diameter: float,
                           y_offset: float = 0, z_offset: float = 0,
                           depth: float = None) -> cq.Workplane:
    """Bohrung von der rechten Seite (+X) aus."""
    return drill_side_hole(body, ">X", diameter, depth, y_offset, z_offset)
```

## Face-Selektor → Bohrrichtung
| Face | Bohrrichtung | X auf Face | Y auf Face |
|------|-------------|-----------|-----------|
| `>X` | von rechts nach links (-X) | Y-Achse | Z-Achse |
| `<X` | von links nach rechts (+X) | Y-Achse | Z-Achse |
| `>Y` | von hinten nach vorne (-Y) | X-Achse | Z-Achse |
| `<Y` | von vorne nach hinten (+Y) | X-Achse | Z-Achse |

## Häufige Fehler
1. **Achsen auf Seitenflächen**: Auf `>X` Face ist X→Y und Y→Z des globalen KS! `.center(10, 5)` bewegt 10mm in Y und 5mm in Z
2. **Tiefe bei Seitenbohrung**: Tiefe geht in Normalenrichtung der Face. Bei `>X` geht die Bohrung in -X Richtung
3. **Face nach Union mehrdeutig**: `>X` nach einer Union kann eine andere Seitenfläche treffen → NearestToPointSelector nutzen

## Komposition
- Seitenbohrung in Platte: `body.faces(">X").workplane(cOBB).hole(d)`
- Bohrung in extrudiertem Steg: Erst Steg erstellen, dann Face des STEGS selektieren
