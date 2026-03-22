# Hole Pattern Grid — Raster-Lochmuster
Tags: lochmuster, lochbild, raster, grid, pattern, rArray, gleichmäßig, reihe, spalte

## Wann verwenden
- User sagt: "Lochraster", "3x4 Löcher", "gleichmäßig verteilt", "Reihen und Spalten"
- Löcher in regelmäßigem X/Y-Raster

## CadQuery Code (modulare Funktion)

```python
def drill_hole_grid(body: cq.Workplane, face_selector: str,
                     diameter: float, depth: float = None,
                     x_spacing: float = 20.0, y_spacing: float = 20.0,
                     x_count: int = 3, y_count: int = 3,
                     offset_x: float = 0, offset_y: float = 0) -> cq.Workplane:
    """Bohrt ein rechteckiges Lochraster.

    Args:
        diameter: Bohrungsdurchmesser (mm)
        depth: Bohrungstiefe (None = durchgehend)
        x_spacing: Abstand zwischen Löchern in X (mm)
        y_spacing: Abstand zwischen Löchern in Y (mm)
        x_count: Anzahl Löcher in X-Richtung
        y_count: Anzahl Löcher in Y-Richtung
    """
    wp = (body.faces(face_selector)
          .workplane(centerOption='CenterOfBoundBox')
          .center(offset_x, offset_y)
          .rArray(x_spacing, y_spacing, x_count, y_count))

    if depth is not None:
        return wp.hole(diameter, depth)
    return wp.hole(diameter)
```

## Parameter-Referenz
| Parameter | Typ | Beschreibung | Default |
|-----------|-----|--------------|---------|
| xSpacing | float | Abstand X-Richtung zwischen Löchern (mm) | — |
| ySpacing | float | Abstand Y-Richtung zwischen Löchern (mm) | — |
| xCount | int | Anzahl Spalten | — |
| yCount | int | Anzahl Reihen | — |

## Varianten
- `.rArray(20, 20, 3, 3).hole(10)`: 3×3 Raster, 20mm Abstand, ∅10mm
- `.rArray(30, 0, 5, 1).hole(8)`: 5 Löcher in einer Reihe, 30mm Abstand
- `.rArray(20, 20, 3, 3).cboreHole(...)`: Raster aus Stufenbohrungen

## Häufige Fehler
1. **Spacing vs. Gesamtmaß**: `rArray(20, 20, 3, 3)` → Gesamtbreite = 2 × 20 = 40mm (nicht 3 × 20 = 60mm). Bei N Löchern gibt es N-1 Abstände
2. **Raster zentriert auf Workplane**: Das Raster wird um den aktuellen Workplane-Ursprung ZENTRIERT
3. **Abstand zu klein**: Wenn x_spacing < diameter → Löcher überlappen → ungültiger Körper
4. **count=1**: Bei nur einer Reihe/Spalte wird das Pattern zur Linie

## Komposition
- Lochraster auf Oberseite: `body.faces(">Z").workplane(cOBB).rArray(...).hole(d)`
- Versetztes Raster: `.center(ox, oy)` vor `.rArray()`
