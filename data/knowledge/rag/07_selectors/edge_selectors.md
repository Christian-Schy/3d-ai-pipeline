# Edge Selectors — Kanten auswählen (für Fillet / Chamfer)
Tags: kante, edge, fillet, chamfer, verrundung, fase, kantenauswahl, abrunden

## Wann verwenden
- Verrundungen (Fillet) oder Fasen (Chamfer) auf bestimmten Kanten
- Nicht alle Kanten, sondern nur bestimmte sollen bearbeitet werden

## CadQuery Code

```python
# Alle Kanten eines Typs
body.edges("|Z")      # Alle vertikalen Kanten (parallel zu Z)
body.edges("#Z")      # Alle Kanten senkrecht zu Z (= horizontale Kanten)
body.edges(">Z")      # Die höchste Kante
body.edges("<Z")      # Die niedrigste Kante

# Kanten einer bestimmten Face
body.faces(">Z").edges()           # Alle Kanten der Oberseite
body.faces(">Z").edges(">X")      # Rechte Kante der Oberseite

# Praktische Funktionen
def fillet_vertical_edges(body: cq.Workplane, radius: float) -> cq.Workplane:
    """Verrundet alle vertikalen Kanten."""
    return body.edges("|Z").fillet(radius)

def fillet_top_edges(body: cq.Workplane, radius: float) -> cq.Workplane:
    """Verrundet nur die Kanten der Oberseite."""
    return body.faces(">Z").edges().fillet(radius)

def fillet_specific_edge(body: cq.Workplane, radius: float,
                          face_sel: str, edge_sel: str) -> cq.Workplane:
    """Verrundet eine spezifische Kante auf einer Face."""
    return body.faces(face_sel).edges(edge_sel).fillet(radius)

def chamfer_bottom_edges(body: cq.Workplane, distance: float) -> cq.Workplane:
    """Fase an den Kanten der Unterseite."""
    return body.faces("<Z").edges().chamfer(distance)
```

## Edge-Selektor-Übersicht
| Selektor | Auswahl |
|----------|---------|
| `\|Z` | Vertikale Kanten (parallel zu Z) |
| `#Z` | Horizontale Kanten (senkrecht zu Z) |
| `>Z` | Höchste Kante |
| `>X` | Rechteste Kante |
| `.faces(">Z").edges()` | Alle Kanten der Oberseite |
| `.faces(">Z").edges(">X")` | Rechte Kante der Oberseite |

## Häufige Fehler
1. **Fillet zu groß**: Radius darf nicht größer als die kürzeste anliegende Kante sein → CadQuery-Error
2. **Fillet nach Boolean**: Nach Union/Cut können neue Kanten entstehen — Selektor prüfen
3. **Reihenfolge**: Fillet/Chamfer IMMER als letztes anwenden (nach allen Booleans und Features)
4. **Chamfer an Verrundung**: Erst Chamfer, dann Fillet — nicht umgekehrt
