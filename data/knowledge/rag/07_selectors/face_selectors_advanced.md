# Face Selectors Advanced — Erweiterte Flächen-Auswahl
Tags: NearestToPointSelector, AreaNthSelector, DirectionNthSelector, advanced, erweitert, spezifisch

## Wann verwenden
- Einfache Selektoren (`>Z`) treffen die falsche Fläche
- Nach Boolean-Operationen mit mehreren Faces auf gleicher Höhe
- Spezifische Face aus mehreren gleichrangigen auswählen

## CadQuery Code

```python
import cadquery as cq
from cadquery.selectors import (
    NearestToPointSelector,
    DirectionNthSelector,
    AreaNthSelector
)

# NearestToPointSelector — Face nächst an einem Punkt
def select_face_near_point(body: cq.Workplane, x: float, y: float, z: float):
    """Wählt die Face deren Zentrum am nächsten an (x,y,z) liegt."""
    return body.faces(NearestToPointSelector((x, y, z)))


# DirectionNthSelector — N-te Face in einer Richtung
def select_nth_face_in_direction(body: cq.Workplane, direction: tuple, n: int = 0):
    """Wählt die n-te Face in einer Richtung (0 = erste/äußerste).

    Args:
        direction: (0,0,1) für Z, (1,0,0) für X etc.
        n: 0 = äußerste, 1 = zweitäußerste, -1 = innerste
    """
    return body.faces(DirectionNthSelector(direction, n))


# AreaNthSelector — Face nach Flächengröße
def select_face_by_area(body: cq.Workplane, n: int = 0):
    """Wählt die n-te Face nach Fläche (0 = größte, -1 = kleinste)."""
    return body.faces(AreaNthSelector(n))


# Praktische Beispiele
def drill_hole_on_specific_top_face(body: cq.Workplane,
                                     target_x: float, target_y: float,
                                     target_z: float,
                                     diameter: float) -> cq.Workplane:
    """Bohrt Loch auf der Top-Face die am nächsten an einem Punkt liegt.

    Nützlich nach Union wenn mehrere Top-Faces existieren.
    """
    return (body.faces(NearestToPointSelector((target_x, target_y, target_z)))
            .workplane(centerOption='CenterOfBoundBox')
            .hole(diameter))
```

## Selektor-Übersicht
| Selektor | Auswahl | Typischer Einsatz |
|----------|---------|-------------------|
| `NearestToPointSelector((x,y,z))` | Face nächst an Punkt | ★ Nach Union, spezifische Face |
| `DirectionNthSelector((0,0,1), 0)` | Äußerste Face in Z | Zweite Stufe von oben: n=1 |
| `DirectionNthSelector((0,0,1), -1)` | Innerste Face in Z | Innere Stufe |
| `AreaNthSelector(0)` | Größte Face | Basis-Face bei komplexem Körper |
| `AreaNthSelector(-1)` | Kleinste Face | Kleines Feature finden |

## Häufige Fehler
1. **NearestToPointSelector Punkt**: Der Punkt muss NICHT auf der Face liegen — er sucht die nächste Face zum Punkt. Gut: Punkt in die Mitte der erwarteten Face setzen
2. **DirectionNthSelector Index**: 0 = äußerste (wie `>Z`), 1 = zweitäußerste, -1 = innerste (wie `<Z`)
3. **Import vergessen**: `from cadquery.selectors import NearestToPointSelector` — nicht automatisch verfügbar
4. **AreaNthSelector bei Zylinder**: Mantelfläche ist oft die größte Face → AreaNthSelector(0) trifft Mantel, nicht Deckel

## Komposition
- Nach Union mit Steg: `NearestToPointSelector((steg_center_x, steg_center_y, top_z))` → trifft die Steg-Oberfläche
- Stufen-Teil: `DirectionNthSelector((0,0,1), 1)` → zweithöchste Fläche = Basis-Oberseite neben Steg
