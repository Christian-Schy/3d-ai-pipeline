# Face Selectors Basic — Flächen auswählen (Grundlagen)
Tags: face, fläche, selektor, auswählen, oben, unten, seite, selector, faces

## Wann verwenden
- Jedes Mal wenn ein Feature auf einer bestehenden Fläche platziert wird
- Bohrungen, Extrusionen, Taschen — alle brauchen eine Face-Selektion
- KRITISCH: Häufigstes Fehlerthema in der Pipeline

## CadQuery Code

```python
# Einfache Richtungsselektoren
body.faces(">Z")    # Höchste Fläche (Oberseite) — die Face mit der größten Z-Koordinate
body.faces("<Z")    # Niedrigste Fläche (Unterseite)
body.faces(">X")    # Rechteste Fläche
body.faces("<X")    # Linkeste Fläche
body.faces(">Y")    # Hinterste Fläche (größtes Y)
body.faces("<Y")    # Vorderste Fläche (kleinstes Y)

# Verwendung mit Workplane
result = (body.faces(">Z")
          .workplane(centerOption='CenterOfBoundBox')
          .hole(10))

# Mehrere Faces selektieren (alle die in eine Richtung zeigen)
body.faces("+Z")    # ALLE Flächen die nach oben zeigen (Normalen in +Z)
body.faces("-Z")    # ALLE Flächen die nach unten zeigen
```

## Selektor-Übersicht
| Selektor | Bedeutung | Beispiel |
|----------|-----------|---------|
| `>Z` | Die EINE Fläche mit der höchsten Z-Position | Oberseite |
| `<Z` | Die EINE Fläche mit der niedrigsten Z-Position | Unterseite |
| `>X` | Die EINE Fläche mit der höchsten X-Position | Rechte Seite |
| `<X` | Die EINE Fläche mit der niedrigsten X-Position | Linke Seite |
| `>Y` | Die EINE Fläche mit der höchsten Y-Position | Rückseite |
| `<Y` | Die EINE Fläche mit der niedrigsten Y-Position | Vorderseite |
| `+Z` | ALLE Flächen mit Normale in +Z Richtung | Alle Oberseiten |
| `-Z` | ALLE Flächen mit Normale in -Z Richtung | Alle Unterseiten |
| `#Z` | ALLE Flächen parallel zur Z-Achse | Alle Seitenflächen |
| `\|Z` | ALLE Flächen senkrecht zur Z-Achse | Ober- + Unterseite |

## KRITISCHE Regel: > vs. + vs. # vs. |
- `>Z` = **extremste** in Z-Richtung (genau EINE Face, die höchste)
- `+Z` = **alle** die in +Z zeigen (können mehrere sein)
- `#Z` = **alle parallel** zur Z-Achse (= Seitenflächen)
- `|Z` = **alle senkrecht** zur Z-Achse (= waagerechte Flächen)

## Häufige Fehler
1. **★★★ Nach Union mehrdeutig**: Wenn zwei Körper gleiche Z-Höhe haben, trifft `>Z` die GRÖSSTE der höchsten Faces — nicht unbedingt die erwartete! → NearestToPointSelector nutzen
2. **> liefert genau EINE Face**: Wenn mehrere Faces auf gleicher Höhe liegen, wird die mit der größten Fläche genommen
3. **+Z vs >Z verwechselt**: `+Z` liefert ALLE nach oben zeigenden Flächen (auch Stufen), `>Z` nur die höchste
4. **Seitenflächen bei Zylinder**: Zylinder-Mantelfläche ist EINE gekrümmte Face, nicht 4 Seiten wie bei Box
5. **Nach .clean()**: Boolean + `.clean()` kann Faces zusammenführen oder aufteilen — Selektoren danach prüfen
