# Boolean Cleanup — .clean() richtig einsetzen
Tags: clean, aufräumen, bereinigen, manifold, boolean_fehler, reparieren

## Wann verwenden
- Nach JEDER Boolean-Operation (union, cut, intersect)
- Wenn STL-Export fehlschlägt ("not manifold")
- Wenn Face-Selektoren nach Boolean unerwartete Ergebnisse liefern

## CadQuery Code

```python
# IMMER nach Boolean
result = body.union(tool).clean()
result = body.cut(tool).clean()
result = body.intersect(tool).clean()

# NICHT nötig nach:
result = body.faces(">Z").workplane().hole(10)  # hole() macht intern clean
result = body.fillet(2)                          # fillet() braucht kein extra clean
result = body.chamfer(1)                         # chamfer() ebenso
```

## Was .clean() macht
1. Entfernt interne Faces (Überbleibsel der Boolean-Berechnung)
2. Führt koplanare Faces zusammen (zwei benachbarte Flächen in gleicher Ebene → eine)
3. Entfernt degenerierte Kanten (Kanten mit Länge 0)
4. Repariert Topologie-Inkonsistenzen

## Wann .clean() Probleme verursachen kann
- Koplanare Faces werden zusammengeführt → Face-Selektion ändert sich
- Sehr kleine Features können verschwinden
- Bei komplexen Geometrien kann .clean() langsam sein

## Häufige Fehler
1. **★ .clean() vergessen**: Häufigster Grund für "non-manifold" STL-Fehler
2. **Zu viele .clean()**: Nach hole(), fillet(), chamfer() ist .clean() unnötig
3. **clean nach .clean() liefert anderes Ergebnis**: Wenn zwei .clean() verschiedene Ergebnisse geben → Geometrie-Problem im Modell
