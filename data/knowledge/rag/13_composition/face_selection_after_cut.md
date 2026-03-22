# Face Selection After Cut — Face-Verhalten nach Schnitten
Tags: face_nach_cut, tasche, bohrung, pocket_face, neue_faces, innenfläche

## Wann verwenden
- Feature auf dem Boden einer Tasche platzieren
- Bohrung im Boden eines Pockets
- Face-Selektion nach cutBlind

## CadQuery Code

```python
from cadquery.selectors import NearestToPointSelector, DirectionNthSelector

# PROBLEM: Nach cutBlind entsteht eine neue Boden-Face
base = cq.Workplane("XY").box(100, 100, 30, centered=(True, True, False))
# Tasche: 40x40, 15mm tief, zentriert
body = (base.faces(">Z")
        .workplane(centerOption='CenterOfBoundBox')
        .rect(40, 40).cutBlind(-15))

# Jetzt existieren ZWEI Faces die nach oben zeigen:
# 1. Die Original-Oberseite (Z=30) MINUS dem Taschenbereich
# 2. Der Taschenboden (Z=15)

# Taschenboden selektieren:
# Methode 1: DirectionNthSelector — zweithöchste +Z Face
pocket_floor = body.faces(DirectionNthSelector((0, 0, 1), 1))

# Methode 2: NearestToPointSelector — Punkt im Taschenboden
pocket_floor = body.faces(NearestToPointSelector((0, 0, 15)))

# Bohrung im Taschenboden
result = (body.faces(NearestToPointSelector((0, 0, 15)))
          .workplane(centerOption='CenterOfBoundBox')
          .hole(8))


# BEISPIEL: Stufentasche (Tasche in Tasche)
def example_stepped_pocket():
    base = cq.Workplane("XY").box(80, 80, 40, centered=(True, True, False))

    # Große Tasche: 50x50, 20mm tief → Boden bei Z=20
    body = (base.faces(">Z").workplane(centerOption='CenterOfBoundBox')
            .rect(50, 50).cutBlind(-20))

    # Kleine Tasche IM Boden der großen: 20x20, 10mm tief → Boden bei Z=10
    body = (body.faces(NearestToPointSelector((0, 0, 20)))
            .workplane(centerOption='CenterOfBoundBox')
            .rect(20, 20).cutBlind(-10))

    return body
```

## Faces nach cutBlind
| Vor Cut | Nach Cut |
|---------|----------|
| 1 Top-Face (Z=30) | Top-Face mit Loch (Z=30) + Taschenboden (Z=15) + 4 Seitenwände |
| `>Z` → Z=30 | `>Z` → Z=30 (immer noch die höchste) |
| — | Taschenboden: `NearestToPointSelector((0,0,15))` |

## Häufige Fehler
1. **>Z trifft nicht den Taschenboden**: >Z gibt immer die HÖCHSTE Face → Original-Oberseite, nicht den Boden
2. **DirectionNthSelector Index**: n=0 = höchste (Oberseite), n=1 = zweithöchste (Taschenboden)
3. **CenterOfBoundBox auf Taschenboden**: Zentrum stimmt nur wenn die Tasche symmetrisch ist
