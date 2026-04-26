# Face-Bestimmung — Richtung, Dimension, Berechnung
Tags: face, seite, fläche, richtung, links, rechts, oben, unten, vorne, hinten

## Direkte Richtungsangaben

| Text | Face |
|------|------|
| "von oben" / "oben" / "Oberseite" | >Z |
| "von unten" / "unten" / "Unterseite" | <Z |
| "von rechts" / "rechte Seite" | >X |
| "von links" / "linke Seite" | <X |
| "von vorne" / "Front" / "vordere" | <Y |
| "von hinten" / "Rückseite" / "hintere" | >Y |
| Keine Angabe | >Z (Standard) |

## Face-Dimensionen einer Box (params x/y/z)

| Face | Dimensionen |
|------|-------------|
| >X / <X (rechts/links) | Y x Z |
| >Y / <Y (hinten/vorne) | X x Z |
| >Z / <Z (oben/unten) | X x Y |

## "von der AxB Seite" — Berechnung

Schritt-für-Schritt:
1. Lies die genannten Maße: "80x40 Seite"
2. Nimm die Parent-Box: x=20, y=80, z=40
3. Berechne jede Face:
   - >X: Y×Z = 80×40 → TREFFER!
   - >Y: X��Z = 20×40
   - >Z: X×Y = 20×80
4. Ergebnis: face=">X"

## Richtungsangaben bei Bohrungen

★ "links brauch ich eine Bohrung" → face="<X"
★ "rechts soll eine Bohrung" → face=">X"
★ "hinten eine Nut" → face=">Y"

Die Richtung DIREKT vor dem Feature-Typ beschreibt die Face!

## "aufrecht"/"hochkant" ändert die Face!

Wenn ein Teil "aufrecht steht", ist die Kontaktfläche NICHT >Z:
- "aufrecht hinten" → face=">Y"
- "aufrecht rechts" → face=">X"
- "aufrecht links" → face="<X"
- "aufrecht" (ohne Richtung) → face=">Y" (Standard)

## Richtungswörter für Position vs. Face

ACHTUNG: Nicht jedes Richtungswort beschreibt die Face!
- "Bohrung von der linken Seite" → face="<X" (Face-Richtung)
- "Bohrung 15mm von der linken Kante" → POSITION auf der aktuellen Face!

Unterscheidung:
- "von [der] linken SEITE/FLÄCHE" = Face-Angabe
- "von [der] linken KANTE/RAND Xmm" = Offset-Angabe
