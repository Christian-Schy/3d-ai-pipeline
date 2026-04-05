# Alignment-Beispiele — Bündig, Zentriert, Offset
Tags: alignment, bündig, flush, centered, offset, position, edge

## Alignment-Werte

| Beschreibung | alignment |
|---|---|
| "mittig" / "zentral" / "zentriert" | "centered" |
| "bündig rechts" / "am rechten Rand" | "flush_right" |
| "bündig links" | "flush_left" |
| "bündig hinten" / "am hinteren Rand" | "flush_top" |
| "bündig vorne" | "flush_bottom" |
| "oben rechts" / "Ecke rechts hinten" | "flush_right_top" |
| "unten links" / "Ecke links vorne" | "flush_left_bottom" |

## Offset-Berechnung bei Abstandsangaben

Wenn die Beschreibung einen KONKRETEN Abstand vom Rand nennt:

"Xmm vom rechten Rand" auf Face >Z:
  → offset_x = +(Parent_X/2 - X)

"Xmm von der Unterkante (-Y)" auf Face >Z:
  → offset_y = -(Parent_Y/2 - X)

"Xmm vom linken Rand" auf Face >Z:
  → offset_x = -(Parent_X/2 - X)

Beispiel: "10mm von Unterkante (-Y)" auf Würfel 30mm:
  → offset_y = -(30/2 - 10) = -(15 - 10) = -5.0

## Wann offset_x/offset_y setzen?

- "zentriert" / "mittig" → offset = null (System berechnet 0)
- "bündig rechts" → offset = null (System berechnet aus Alignment)
- "10mm vom Rand" → offset EXPLIZIT berechnen und setzen!
- "5mm nach rechts versetzt" → offset_x = 5.0

## Face-abhängige Achsen

Auf >Z Face: offset_x = X-Richtung, offset_y = Y-Richtung
Auf >X Face: offset_x = Y-Richtung, offset_y = Z-Richtung
Auf >Y Face: offset_x = X-Richtung, offset_y = Z-Richtung
