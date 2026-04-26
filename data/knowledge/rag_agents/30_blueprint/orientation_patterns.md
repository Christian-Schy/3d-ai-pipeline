# Orientierung — Hochkant, Stehend, Liegend, Achsen-Umordnung
Tags: aufrecht, stehend, hochkant, liegend, orientation, drehen, achse

## Wann wird die Orientierung geändert?

Wenn die Spec beschreibt, dass ein Teil NICHT in Standard-Orientierung ist:
- "hochkant" / "stehend" / "aufrecht" → größte Dim wird Z
- "AxB Fläche liegt auf" → A wird X, B wird Y, Rest wird Z
- "N gehts nach oben" / "N hoch" → Dimension N wird Z

## "hochkant"/"stehend"/"aufrecht"

Die GRÖSSTE Dimension wird Z (Höhe).

Beispiel: Platte 60×60×20 "hochkant"
→ Original: x=60, y=60, z=20
→ Neu: x=60, y=20, z=60 (größte Dim 60 geht nach Z)

Beispiel: Platte 20×80×40 "hochkant"
→ Original: x=20, y=80, z=40
→ Neu: x=20, y=40, z=80 (größte Dim 80 geht nach Z)

## "AxB Fläche liegt auf"

Die genannten Maße A und B werden X und Y, der Rest wird Z.

Beispiel: 20×80×40 "20×80 liegt auf"
→ x=20, y=80, z=40 (20→X, 80→Y, 40→Z)

Beispiel: 20×80×40 "80×40 liegt auf"
→ x=80, y=40, z=20 (80→X, 40→Y, 20→Z)

## "N gehts nach oben" / "N hoch"

Die genannte Dimension N wird Z.

Beispiel: 20×80×40 "80 hoch"
→ x=20, y=40, z=80

## Face-Änderung bei "aufrecht"

★ ACHTUNG: "aufrecht" ändert auch die Face!

| Beschreibung | Face |
|---|---|
| "aufrecht hinten" | >Y |
| "aufrecht vorne" | <Y |
| "aufrecht rechts" | >X |
| "aufrecht links" | <X |
| "aufrecht" (ohne Richtung) | >Y (Standard) |

FALSCH: "aufrecht hinten bündig" → face=">Z"
RICHTIG: "aufrecht hinten bündig" → face=">Y"

Das Teil steht senkrecht, die Kontaktfläche ist eine Y- oder X-Face!

## Reihenfolge der Verarbeitung

1. Maße WÖRTLICH aus Spec lesen: "Platte 20×80×40" → x=20, y=80, z=40
2. Orientierungs-Umordnung DANACH anwenden
3. Face aus Orientierung + Richtung bestimmen
