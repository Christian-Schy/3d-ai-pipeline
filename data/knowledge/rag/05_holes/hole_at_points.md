# Hole at Points — Bohrungen an beliebigen Positionen
Tags: pushPoints, positionen, beliebig, koordinaten, mehrere_löcher, custom, frei

## Wann verwenden
- Löcher an nicht-regelmäßigen Positionen
- User gibt explizite Koordinaten für jedes Loch
- Ecken, asymmetrische Muster

## CadQuery Code (modulare Funktion)

```python
def drill_holes_at_points(body: cq.Workplane, face_selector: str,
                           diameter: float, positions: list,
                           depth: float = None) -> cq.Workplane:
    """Bohrt Löcher an beliebigen Positionen auf einer Fläche.

    Args:
        diameter: Bohrungsdurchmesser (mm)
        positions: Liste von (x, y) Tupeln relativ zum Face-Zentrum
        depth: Bohrungstiefe (None = durchgehend)
    """
    wp = (body.faces(face_selector)
          .workplane(centerOption='CenterOfBoundBox')
          .pushPoints(positions))

    if depth is not None:
        return wp.hole(diameter, depth)
    return wp.hole(diameter)


def drill_corner_holes(body: cq.Workplane, face_selector: str,
                        diameter: float, inset: float,
                        body_width: float, body_length: float,
                        depth: float = None) -> cq.Workplane:
    """Bohrt 4 Löcher in die Ecken einer rechteckigen Fläche.

    Args:
        inset: Abstand von den Ecken (mm) — Lochmittelpunkt zum Rand
        body_width: Breite des Körpers in X (mm)
        body_length: Länge des Körpers in Y (mm)
    """
    half_w = body_width / 2 - inset
    half_l = body_length / 2 - inset
    positions = [
        ( half_w,  half_l),   # oben rechts
        (-half_w,  half_l),   # oben links
        ( half_w, -half_l),   # unten rechts
        (-half_w, -half_l),   # unten links
    ]
    return drill_holes_at_points(body, face_selector, diameter, positions, depth)
```

## Parameter-Referenz
| Parameter | Typ | Beschreibung | Default |
|-----------|-----|--------------|---------|
| points | list[(x,y)] | Positionen relativ zum Workplane-Ursprung | — |

## Varianten
- Eckbohrungen: `drill_corner_holes()` wie oben
- Einzelne Positionen: `.pushPoints([(10, 20), (-15, 30)]).hole(d)`
- Kombination mit center: `.center(ox, oy).pushPoints([...])` — verschiebt ALLE Punkte

## Häufige Fehler
1. **★ Koordinaten relativ zum Workplane-Ursprung**: Bei `centerOption='CenterOfBoundBox'` ist (0,0) die Face-Mitte. Eckbohrungen = ±(width/2 - inset)
2. **Punkte außerhalb der Face**: Wenn (x,y) außerhalb der Face liegt → Bohrung geht ins Leere
3. **center() vor pushPoints()**: `.center(10, 0).pushPoints([(0,0)])` → Loch bei (10, 0), nicht bei (0, 0)
4. **Einzel-Bohrung via pushPoints**: Für EIN Loch besser `.center(x, y).hole(d)` statt `.pushPoints([(x,y)]).hole(d)`
5. **★ 3D Tupel in pushPoints**: `pushPoints([(x, y, z)])` schlägt fehl — pushPoints akzeptiert nur 2D `(x, y)` relativ zur Workplane!
6. **★ body.cut(workplane.hole())**: FALSCH — `.hole()` schneidet den Body bereits intern. NIEMALS `body.cut(wp.pushPoints([...]).hole(d))` wrappen. Stattdessen direkt ketten: `body.faces(">Z").workplane(centerOption='CenterOfBoundBox').pushPoints([(x, y)]).hole(d)`

## Komposition
- 4 Ecken: `drill_corner_holes()` — häufigstes Muster bei Platten
- Auf Feature: Erst Face des Features selektieren, dann pushPoints relativ dazu
