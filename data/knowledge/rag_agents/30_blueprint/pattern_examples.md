# Bohrungsmuster — Grid, Circular, Linear
Tags: pattern, muster, bohrung, reihe, lochkreis, eckbohrungen, linear, grid, circular

## hole_pattern_grid — Eckbohrungen / Raster

Trigger: "in jede Ecke", "Eckbohrungen", "4 Bohrungen am Rand"

Parameter:
- count: Anzahl (4 = 2x2, 6 = 3x2, 9 = 3x3)
- inset: Abstand vom Rand in mm
- hole_diameter: Durchmesser jeder Bohrung
- depth: Tiefe (null = durchgehend)

Beispiel: "Platte 80x80x20, in jede Ecke 15mm vom Rand eine Bohrung 8mm durchgehend"
```json
{
  "type": "hole_pattern_grid",
  "params": {"count": 4, "inset": 15, "hole_diameter": 8, "depth": null},
  "parent": "base",
  "placement": {"face": ">Z", "alignment": "centered", "offset_x": 0, "offset_y": 0},
  "operation": "subtract"
}
```

## hole_pattern_circular — Lochkreis

Trigger: "Lochkreis", "Bohrungen auf einem Kreis", "kreisförmig angeordnet"

Parameter:
- bolt_circle_diameter: Durchmesser des Teilkreises
- count: Anzahl Bohrungen
- hole_diameter: Durchmesser jeder Bohrung
- depth: Tiefe (null = durchgehend)

Beispiel: "Lochkreis ∅60 mit 6 Bohrungen ∅8 durchgehend"
```json
{
  "type": "hole_pattern_circular",
  "params": {"bolt_circle_diameter": 60, "count": 6, "hole_diameter": 8, "depth": null},
  "parent": "base",
  "placement": {"face": ">Z", "alignment": "centered", "offset_x": 0, "offset_y": 0},
  "operation": "subtract"
}
```

## hole_pattern_linear — Bohrungsreihe

Trigger: "X Bohrungen im Abstand", "Bohrungen in einer Reihe", "gleichmäßig verteilt"

Parameter:
- count: Anzahl Bohrungen
- spacing: Abstand zwischen Bohrungen (Mitte zu Mitte)
- start_offset: Abstand der ersten Bohrung vom linken/unteren Rand
- hole_diameter: Durchmesser jeder Bohrung
- depth: Tiefe (null = durchgehend)
- direction: "x" oder "y" (Richtung der Reihe auf der Face)

Beispiel: "Platte 20x40x200, rechte Fläche, ab 40mm vom Rand 4 Bohrungen im Abstand 20mm, ∅10, 10mm tief"
```json
{
  "type": "hole_pattern_linear",
  "params": {"count": 4, "spacing": 20, "start_offset": 40, "hole_diameter": 10, "depth": 10, "direction": "y"},
  "parent": "base",
  "placement": {"face": ">X", "alignment": "centered", "offset_x": 0, "offset_y": 0},
  "operation": "subtract"
}
```

★ WICHTIG: "ab 40mm vom Rand" = start_offset=40 (vom linken/unteren Rand der Face gemessen)
★ direction bestimmt entlang welcher Face-Achse die Reihe verläuft

## Unterscheidung: Wann welches Muster?

| Beschreibung | Typ |
|---|---|
| "in jede Ecke" / "4 Eckbohrungen" | hole_pattern_grid |
| "Lochkreis" / "auf einem Kreis" | hole_pattern_circular |
| "in einer Reihe" / "im Abstand von Xmm" | hole_pattern_linear |
| "eine Bohrung" (einzeln) | hole_single |

★ NIEMALS ein Muster in einzelne hole_single aufteilen!
