# Geometrie-Regeln — Koordinatensystem, Stacking, Berechnung
Tags: geometrie, koordinaten, stacking, höhe, berechnung, maße

## Koordinatensystem

Box mit centered=(True, True, False):
- X-Achse: [-W/2 .. +W/2] (links ↔ rechts)
- Y-Achse: [-L/2 .. +L/2] (vorne ↔ hinten)
- Z-Achse: [0 .. H] (unten → oben)

Nullpunkt: Mitte der Grundfläche, auf dem Boden.

## Maße-Extraktion

Maße WÖRTLICH aus der Spezifikation lesen:
- "Platte 20×80×40" → x=20, y=80, z=40
- "∅10mm durchgehend" → diameter=10, depth=null
- "∅10mm 29mm tief" → diameter=10, depth=29
- "Nut 5×5" → width=5, depth=5, length=null
- "Nut 5×5 entlang Y 30mm lang" → width=5, depth=5, length=30
- "50mm Würfel" → x=50, y=50, z=50

★ ERST wörtlich lesen, DANN Orientierung anwenden!

## Parameter-Formate

| Typ | Parameter |
|---|---|
| Box/Plate | x, y, z |
| Cylinder | diameter ODER radius, height |
| Hole | diameter, depth (null=Durchgang) |
| Slot/Groove | width, depth, length (null=volle Länge) |
| Pattern Grid | inset, count, hole_diameter, depth |
| Pattern Circular | bolt_circle_diameter, count, hole_diameter, depth |
| Pattern Linear | spacing, count, start_offset, hole_diameter, depth, direction |
| Fillet | radius |
| Chamfer | size |
| Shell | thickness |
| Angled | x, y, z, angle_deg, reference_edge |

## Z-Stacking

Wenn Features übereinander gestapelt werden:
- Jedes Feature sitzt auf der >Z Face seines Parents
- Höhe des Stapels = Summe aller z-Werte
- Child Z beginnt wo Parent Z endet

## Nut-Besonderheiten

★ "length" MUSS immer gesetzt werden:
- Nut über volle Länge → length=null
- Nut mit Maß → length=Zahl
- "entlang Y" → direction/notes angeben

## Durchgangsbohrung vs. Sackloch

- "durchgehend" / "Durchgangsbohrung" → depth=null
- "Xmm tief" / "Sackloch" → depth=X
- Keine Angabe → depth=null (Standard: Durchgang)
