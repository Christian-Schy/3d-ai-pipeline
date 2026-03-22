# Workplane- und Face-Selektionsregeln

## Einfache Selektoren (sicher VOR Union)
- ">Z" → höchste Z-Fläche (Oberseite)
- "<Z" → tiefste Z-Fläche (Unterseite)
- ">X" → rechteste X-Fläche
- "<X" → linkeste X-Fläche
- ">Y" → vorderste Y-Fläche
- "<Y" → hinterste Y-Fläche

## NearestToPoint (nach Union erforderlich)
Wenn nach einer Union mehrere gleichhohe Flächen existieren:
selector_point = [center_x, center_y, top_z]

Beispiel: Steg der Breite 20 auf Basis-Top bei z=10, Steg-Höhe=15:
- Steg-Mitte: center_x, center_y (Positionskoordinaten)
- Steg-Top: top_z = 10 + 15 = 25
- selector_point = [center_x, center_y, 25]

## Placement-Werte im Blueprint
placement.face: ">Z" | ">X" | "<X" | ">Y" | "<Y" | "NearestToPoint"
placement.selector_point: [x, y, z] — nur wenn face="NearestToPoint"
placement.position: "center" | "flush_right" | "flush_left" | "corners" | "offset"
placement.offset_x: float — Abstand von Flächenmitte in X
placement.offset_y: float — Abstand von Flächenmitte in Y

## Wann NearestToPoint zwingend?
- Nach jeder Union (body.union())
- Wenn mehrere Flächen auf gleicher Höhe existieren
- Für Features auf aufgesetzten Körpern (Steg, Boss)
