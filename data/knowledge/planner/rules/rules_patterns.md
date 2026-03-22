# Muster- und Pattern-Regeln

## Wann welcher Pattern-Typ
- Gleichmäßiges Raster (NxM): hole_pattern_grid
- Kreis/Lochkreis: hole_pattern_circular
- "4 Löcher in den Ecken": hole_pattern_grid, x_count=2, y_count=2
- "Löcher alle Xmm": hole_pattern_grid mit x_spacing=X

## hole_pattern_grid Parameter
- x_count: Anzahl Löcher in X-Richtung
- y_count: Anzahl Löcher in Y-Richtung
- x_spacing: Abstand Mitte-Mitte in X (mm)
- y_spacing: Abstand Mitte-Mitte in Y (mm)
- diameter: Lochdurchmesser
- depth: Tiefe (null=durch)

Raster-Breite = (x_count-1) * x_spacing
Raster-Position auf Fläche: offset_x/y zum Raster-Mittelpunkt

## hole_pattern_circular Parameter
- circle_diameter: Durchmesser des Lochkreises (Mitte-zu-Mitte der Löcher)
- n_holes: Anzahl gleichmäßig verteilter Löcher
- diameter: Lochdurchmesser
- depth: Tiefe (null=durch)
Lochkreis Regel: circle_d/2 + hole_d/2 < parent_min_dim/2

## Ecklöcher-Berechnung
Loch in Ecke mit Randabstand r:
- Basis: W x L
- offset_x = W/2 - r (Abstand von Mitte)
- offset_y = L/2 - r
- x_spacing = W - 2*r (Abstand zwischen den 2 Löchern in X)
- y_spacing = L - 2*r
