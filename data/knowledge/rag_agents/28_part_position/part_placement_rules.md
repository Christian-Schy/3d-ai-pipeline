# Part Placement Rules — Grundregeln
Tags: placement, face, alignment, aufsatz, seitlich, oben, unten, position

## Face-Zuordnung aus Sprache

| Beschreibung | Face |
|---|---|
| "oben" / "auf" / "drauf" / "auf der Oberseite" | >Z |
| "unten" / "unter" / "Unterseite" | <Z |
| "rechts" / "rechte Seite" / "an der rechten Seite" | >X |
| "links" / "linke Seite" / "an der linken Seite" | <X |
| "hinten" / "Rückseite" / "hintere Seite" | >Y |
| "vorne" / "Front" / "Vorderseite" | <Y |

## Face-Dimensionen einer Box (x/y/z)

- >Z und <Z (Ober-/Unterseite): Maße = X x Y
- >X und <X (rechts/links): Maße = Y x Z
- >Y und <Y (hinten/vorne): Maße = X x Z

## Alignment-Werte

| Beschreibung | alignment |
|---|---|
| "mittig" / "zentral" / keine Angabe | "centered" |
| "bündig rechts" / "am rechten Rand" | "flush_right" |
| "bündig links" / "am linken Rand" | "flush_left" |
| "bündig hinten" / "hinterer Rand" | "flush_top" |
| "bündig vorne" / "vorderer Rand" | "flush_bottom" |

## Standard-Fälle

### Aufsatz oben (Standard)
"Platte auf Basis" / "oben drauf" / "auf der Oberseite"
-> face=">Z", alignment="centered"

### Seitlich rechts bündig
"Platte rechts an die Basis" / "bündig rechts"
-> face=">Z", alignment="flush_right"
(Wenn "auf" implizit, face bleibt >Z, alignment bestimmt die Seite)

### Seitlich AN der Seite (nicht oben)
"Platte AN der rechten Seite" / "seitlich rechts angebaut"
-> face=">X", alignment="centered"

## Zusammengesetzte Positionen

"oben rechts bündig" -> face=">Z", alignment="flush_right"
"oben hinten bündig" -> face=">Z", alignment="flush_top"
"oben links vorne" -> face=">Z", alignment="flush_left", offset_y nötig
"rechts oben bündig" -> face=">Z", alignment="flush_right" (oben=face, rechts=alignment)

MERKE: "oben" bestimmt die Face (>Z), Richtungswörter bestimmen Alignment!
