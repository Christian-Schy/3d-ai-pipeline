# Bolt Circle Geometry — Lochkreis-Geometrie für den Planner
Tags: lochkreis, bolt_circle, geometrie, berechnung, radius

## ★ HÄUFIGSTER FEHLER: Radius vs. Durchmesser

User sagt: "Lochkreis ∅60mm mit 6 Löchern ∅10mm"
- Teilkreis-DURCHMESSER = 60mm
- Teilkreis-RADIUS = 30mm ← für Positionsberechnung!
- Loch-DURCHMESSER = 10mm
- Loch-RADIUS = 5mm

## Positionen berechnen

Gegeben: Teilkreis-Durchmesser D, Anzahl N, Startwinkel S (default 0°)
Radius R = D / 2

Position i (für i = 0 bis N-1):
  x_i = R × cos(S + i × 360° / N)
  y_i = R × sin(S + i × 360° / N)

## Plausibilitätsprüfung
1. Teilkreis-R + Loch-R < Parent-Breite/2
   (Löcher dürfen nicht über den Rand ragen)
2. Abstand zwischen Löchern > Loch-Durchmesser
   (Abstand ≈ 2 × R × sin(π/N) > Loch-D)
3. N ≥ 2 (sonst Einzelbohrung)

## Startwinkel
- 0° = erstes Loch rechts (+X)
- 90° = erstes Loch oben (+Y)
- User sagt nichts → Default 0°

## Im Feature Tree
```json
{
  "type": "hole_pattern_circular",
  "params": {
    "circle_diameter": 60,
    "hole_diameter": 10,
    "n_holes": 6,
    "start_angle": 0,
    "depth": null
  }
}
```
IMMER circle_diameter (NICHT radius) im Blueprint — der Coder rechnet um.
