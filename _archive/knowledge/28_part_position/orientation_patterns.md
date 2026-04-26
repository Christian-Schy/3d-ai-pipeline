# Orientierung — Aufrecht, Stehend, Hochkant, Liegend
Tags: aufrecht, stehend, hochkant, liegend, orientation, orientierung, senkrecht, vertikal

## Warum Orientierung wichtig ist

Wenn ein Teil "aufrecht" / "stehend" / "hochkant" steht, ändert sich welche
Dimension nach oben zeigt. Der Blueprint Assembler dreht die Maße entsprechend.

Der Part Position Assigner muss nur den orientation_hint WÖRTLICH weitergeben!

## orientation_hint — Wörtlich übernehmen!

| Beschreibung in Spec | orientation_hint |
|---|---|
| "aufrecht" | "aufrecht" |
| "stehend" | "stehend" |
| "hochkant" | "hochkant" |
| "20×80 Fläche liegt auf" | "20×80 Fläche liegt auf" |
| "80 gehts nach oben" | "80 gehts nach oben" |
| "die lange Seite zeigt hoch" | "die lange Seite zeigt hoch" |
| nichts angegeben | null |

## Face-Bestimmung bei "aufrecht"

ACHTUNG: "aufrecht" ändert die Face!

FALSCH: "aufrecht hinten bündig" -> face=">Z" (das wäre liegend!)
RICHTIG: "aufrecht hinten bündig" -> face=">Y", orientation_hint="aufrecht"

Warum? Das Teil steht senkrecht, also ist die Kontaktfläche eine Y- oder X-Face.

### Regeln:
- "aufrecht" + "hinten" / "an der Rückseite" -> face=">Y"
- "aufrecht" + "vorne" / "an der Front" -> face="<Y"
- "aufrecht" + "rechts" -> face=">X"
- "aufrecht" + "links" -> face="<X"
- "aufrecht" ohne Richtung -> face=">Y" (Standard: hinten)

## Beispiel: Platte 180×180×20 aufrecht hinten

Spec: "Platte 180×180×20mm oben hinten aufrecht und bündig"
Parent: base 180×180×20

Ergebnis:
```json
{
  "face": ">Y",
  "alignment": "flush_top",
  "orientation_hint": "aufrecht"
}
```

## Beispiel: Platte 20×80×40 mit "80 gehts nach oben"

Spec: "Platte 20×80×40mm rechts auf Basis, 20×80 liegt auf, bündig rechts"
Parent: base 100×100×20

Ergebnis:
```json
{
  "face": ">Z",
  "alignment": "flush_right",
  "orientation_hint": "20×80 Fläche liegt auf"
}
```

## face_hint — Wenn Maße die Face bestimmen

Wenn die Spec sagt "von der 80×40 Seite" oder "an der 100×20 Fläche":
-> face_hint = "von der 80×40 Seite" (wörtlich!)

Der Blueprint Assembler berechnet dann deterministisch welche Face
diese Dimensionen hat und korrigiert wenn nötig.
