# Vertex Selectors — Eckpunkte auswählen
Tags: vertex, punkt, ecke, eckpunkt, corner, selektieren

## Wann verwenden
- Bezugspunkt für Messungen oder Positionierung
- Selten direkt für Features, häufiger für Referenzierung
- Fillet/Chamfer an bestimmten Ecken

## CadQuery Code

```python
# Richtungsselektoren (wie bei Faces)
body.vertices(">Z")     # Höchster Punkt
body.vertices("<Z")     # Niedrigster Punkt
body.vertices(">X")     # Rechtester Punkt
body.vertices(">(1,1,1)")  # Nächster Punkt in Richtung (1,1,1) = oben-rechts-hinten

# Alle Vertices einer Face
body.faces(">Z").vertices()        # Alle Eckpunkte der Oberseite
body.faces(">Z").vertices(">X")   # Rechter oberer Eckpunkt der Oberseite

# Praktisch: BoundingBox-Ecken
def get_corner_points(body: cq.Workplane) -> dict:
    """Gibt die BoundingBox-Eckpunkte zurück."""
    bb = body.val().BoundingBox()
    return {
        'min': (bb.xmin, bb.ymin, bb.zmin),
        'max': (bb.xmax, bb.ymax, bb.zmax),
        'center': (bb.center.x, bb.center.y, bb.center.z),
    }
```

## Häufige Fehler
1. **Vertices sind Punkte, nicht Flächen**: Auf Vertices kann man keine Workplane setzen (direkt)
2. **Zylinder haben wenige Vertices**: Kreis-Kanten können 0 oder 2 Vertices haben
3. **Fillet an Vertex**: CadQuery unterstützt kein Fillet direkt an Vertices — Kante selektieren stattdessen
