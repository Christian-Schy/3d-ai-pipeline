# Workplane on Child Feature — Workplane auf Sub-Feature setzen
Tags: workplane_auf_feature, sub_feature, child, verschachtelt, arbeitsebene_feature

## Wann verwenden
- Workplane auf der Oberseite/Seite eines Features setzen (nicht der Basis)
- Mehrere Features übereinander stapeln
- Exakte Positionierung auf einem kleinen Feature

## CadQuery Code

```python
from cadquery.selectors import NearestToPointSelector

def get_workplane_on_child(body: cq.Workplane,
                            feature_x: float, feature_y: float,
                            feature_z: float) -> cq.Workplane:
    """Erstellt Workplane auf der Face eines Child-Features.

    Args:
        feature_x/y/z: Punkt auf der Ziel-Face des Features
                        (möglichst nahe am Zentrum der Face)
    """
    return (body.faces(NearestToPointSelector((feature_x, feature_y, feature_z)))
            .workplane(centerOption='CenterOfBoundBox'))


# Beispiel: 3 Stufen übereinander
def example_three_steps():
    # Stufe 1: 100x100x10
    body = cq.Workplane("XY").box(100, 100, 10, centered=(True, True, False))

    # Stufe 2: 60x60x10, oben auf Stufe 1
    body = (body.faces(">Z")  # Hier OK: nur eine Top-Face
            .workplane(centerOption='CenterOfBoundBox')
            .rect(60, 60).extrude(10))
    # Stufe 2 Top bei Z=20

    # Stufe 3: 30x30x10, oben auf Stufe 2
    # JETZT brauchen wir NearestToPointSelector!
    body = (body.faces(NearestToPointSelector((0, 0, 20)))
            .workplane(centerOption='CenterOfBoundBox')
            .rect(30, 30).extrude(10))
    # Stufe 3 Top bei Z=30

    return body
```

## Wann ist NearestToPointSelector NÖTIG?
| Situation | >Z reicht? | NearestToPointSelector nötig? |
|-----------|-----------|------------------------------|
| Erstes Feature auf Basis | ✓ Ja | Nein |
| Nach 1. Union (gleiche Höhe) | ✗ Nein | ★ Ja |
| Nach 1. Union (Aufsatz höher) | Trifft Aufsatz | ★ Ja wenn Basis gewollt |
| Nach extrude() auf Face | Trifft Extrusion | ★ Ja wenn andere Face gewollt |

## Häufige Fehler
1. **Z-Koordinate des Punkts**: Muss die Z-Höhe der ZIEL-FACE sein, nicht die Gesamthöhe
2. **Punkt zu ungenau**: Wenn zwei Faces ähnliche Zentren haben → Punkt genauer setzen
3. **extrude() combine=True**: Nach `.extrude()` auf einer Face ist >Z die neue Extrusionsoberseite
