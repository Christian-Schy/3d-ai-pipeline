# Face Selectors By Type — Parallel / Senkrecht / Richtung
Tags: parallel, senkrecht, perpendicular, type_selector, hash, pipe, seitenflächen, mantelfläche

## Wann verwenden
- Alle Seitenflächen eines Körpers auswählen (für Fillet, Shell)
- Alle waagerechten Flächen auswählen
- Flächen nach Orientierung filtern

## CadQuery Code

```python
# Typ-Selektoren
body.faces("#Z")    # Alle Flächen PARALLEL zur Z-Achse (= Seitenflächen)
body.faces("|Z")    # Alle Flächen SENKRECHT zur Z-Achse (= Ober/Unterseite)
body.faces("#X")    # Alle Flächen parallel zur X-Achse
body.faces("|X")    # Alle Flächen senkrecht zur X-Achse (= links/rechts)

# Richtungsselektoren (+ / -)
body.faces("+Z")    # Alle Flächen mit Normale in +Z (nach oben zeigend)
body.faces("-Z")    # Alle Flächen mit Normale in -Z (nach unten zeigend)

# Praktische Beispiele
def fillet_all_vertical_edges(body: cq.Workplane, radius: float) -> cq.Workplane:
    """Verrundet alle vertikalen Kanten."""
    return body.edges("|Z").fillet(radius)

def fillet_top_edges_only(body: cq.Workplane, radius: float) -> cq.Workplane:
    """Verrundet nur die Kanten der Oberseite."""
    return body.faces(">Z").edges().fillet(radius)
```

## Übersicht: # vs. | vs. + vs. - vs. > vs. <
| Selektor | Bedeutung | Anzahl Ergebnisse |
|----------|-----------|-------------------|
| `>Z` | Extremste (höchste) in Z | Genau 1 |
| `<Z` | Extremste (niedrigste) in Z | Genau 1 |
| `+Z` | Alle mit Normale in +Z | 1 oder mehr |
| `-Z` | Alle mit Normale in -Z | 1 oder mehr |
| `#Z` | Alle parallel zur Z-Achse | 0 oder mehr |
| `\|Z` | Alle senkrecht zur Z-Achse | 1 oder mehr |

## Häufige Fehler
1. **# und | verwechselt**: `#Z` = parallel zu Z = SEITENFLÄCHEN, `|Z` = senkrecht zu Z = OBER/UNTERSEITE
2. **+Z vs >Z**: `+Z` gibt ALLE nach oben zeigenden Faces (bei Stufen mehrere!), `>Z` nur die höchste
3. **Zylinder-Mantelfläche**: Bei Zylindern ist `#Z` die Mantelfläche, `|Z` sind Deckel + Boden
