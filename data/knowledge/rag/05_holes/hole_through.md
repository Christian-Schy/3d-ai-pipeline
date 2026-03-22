# Hole Through — Durchgangsbohrung
Tags: durchgangsbohrung, through_hole, durchgehend, bohrung, loch

## Wann verwenden
- User sagt: "Durchgangsbohrung", "durchgehendes Loch", "Bohrung durch"
- Loch geht komplett durch das Material

## CadQuery Code (modulare Funktion)

```python
def drill_through_hole(body: cq.Workplane, face_selector: str,
                        diameter: float,
                        offset_x: float = 0, offset_y: float = 0) -> cq.Workplane:
    """Bohrt eine Durchgangsbohrung.

    Args:
        diameter: Durchmesser in mm
    """
    return (body.faces(face_selector)
            .workplane(centerOption='CenterOfBoundBox')
            .center(offset_x, offset_y)
            .hole(diameter))


def drill_through_hole_at_point(body: cq.Workplane, face_selector: str,
                                 diameter: float,
                                 x: float, y: float) -> cq.Workplane:
    """Durchgangsbohrung an absoluter Position auf der Face."""
    return (body.faces(face_selector)
            .workplane(centerOption='CenterOfBoundBox')
            .center(x, y)
            .hole(diameter))
```

## Parameter-Referenz
| Parameter | Typ | Beschreibung | Default |
|-----------|-----|--------------|---------|
| diameter | float | Bohrungsdurchmesser in mm | — |

## Varianten
- `.hole(diameter)`: Ohne depth-Parameter = automatisch durchgehend
- `.circle(radius).cutThruAll()`: Alternative, gibt mehr Kontrolle über Richtung

## Häufige Fehler
1. **hole() ohne depth geht in BEIDE Richtungen**: Bei gestapelten Körpern durchbohrt es alles
2. **Face-Selektor trifft falsche Fläche**: Nach Union mit mehreren Körpern kann `>Z` die falsche Top-Face treffen → NearestToPointSelector nutzen
3. **Position relativ zu CenterOfBoundBox**: `center(10, 0)` ist 10mm RECHTS von der Face-Mitte, nicht 10mm vom Ursprung

## Komposition
- Zentrale Bohrung: `body.faces(">Z").workplane(cOBB).hole(d)`
- Versetzte Bohrung: `body.faces(">Z").workplane(cOBB).center(ox, oy).hole(d)`
