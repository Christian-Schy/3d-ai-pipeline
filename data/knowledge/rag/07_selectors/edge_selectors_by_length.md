# Edge Selectors By Length — Kanten nach Länge auswählen
Tags: kante, länge, edge_length, EdgeLengthNthSelector, spezifisch, fillet_kante

## Wann verwenden
- Fillet/Chamfer nur auf der längsten oder kürzesten Kante
- Spezifische Kante über ihre Länge identifizieren

## CadQuery Code

```python
from cadquery.selectors import EdgeLengthNthSelector

# Längste Kante
body.edges(EdgeLengthNthSelector(0))           # Index 0 = längste
# Kürzeste Kante
body.edges(EdgeLengthNthSelector(-1))          # Index -1 = kürzeste
# Zweitlängste
body.edges(EdgeLengthNthSelector(1))           # Index 1 = zweitlängste

# Praktisch: Fillet nur auf den 4 längsten Kanten
def fillet_longest_edges(body: cq.Workplane, radius: float,
                          n: int = 4) -> cq.Workplane:
    """Verrundet die n längsten Kanten."""
    for i in range(n):
        try:
            body = body.edges(EdgeLengthNthSelector(i)).fillet(radius)
        except Exception:
            break
    return body

# Kanten einer Face nach Länge
body.faces(">Z").edges(EdgeLengthNthSelector(0))  # Längste Kante der Oberseite
```

## Häufige Fehler
1. **Index-Richtung**: 0 = längste, -1 = kürzeste (absteigend sortiert)
2. **Fillet auf eine Kante nach der anderen**: Jeder Fillet ändert die Topologie → Selektoren können sich ändern
3. **Kanten nach Boolean**: Union/Cut erzeugen neue Kanten → Längenranking ändert sich
