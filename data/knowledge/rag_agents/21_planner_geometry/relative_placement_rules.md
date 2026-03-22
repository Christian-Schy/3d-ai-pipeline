# Relative Placement Rules — ★ Parent-Face + Offset-Logik
Tags: placement, relativ, parent, face, offset, position

## Placement-Objekt im Feature Tree

```json
"placement": {
  "face": ">Z",
  "position": "center",
  "offset_x": 0,
  "offset_y": 0
}
```

## Face-Wahl nach Kontext
| User sagt | face |
|-----------|------|
| "oben drauf" / "auf der Oberseite" | >Z |
| "unten drunter" | <Z |
| "von rechts" / "rechte Seite" | >X |
| "von links" | <X |
| "von hinten" | >Y |
| "von vorne" | <Y |
| "darin" (vertikal) | >Z des Parents |
| "darin seitlich" | >X oder <X des Parents |

## Position-Werte
| Wert | Bedeutung |
|------|-----------|
| `center` | Mitte der Parent-Face |
| `flush_right` | Bündig am +X Rand |
| `flush_left` | Bündig am -X Rand |
| `flush_back` | Bündig am +Y Rand |
| `flush_front` | Bündig am -Y Rand |
| `corners` | 4 Eckpositionen (für Lochbilder) |
| `offset` | Benutzerdefinierter Versatz (offset_x, offset_y angeben) |

## Offset-Berechnung

### Auf >Z Face (Draufsicht)
offset_x → verschiebt in globales X (+ = rechts)
offset_y → verschiebt in globales Y (+ = hinten)

### Auf >X Face (Seitenansicht von rechts)
offset_x → verschiebt in globales Y
offset_y → verschiebt in globales Z

### Auf >Y Face (Rückansicht)
offset_x → verschiebt in globales X
offset_y → verschiebt in globales Z

## WICHTIG: Placement ist RELATIV zum Parent
- "center" = Mitte der Parent-Face, NICHT globaler Ursprung
- "flush_right" = rechter Rand des PARENTS, nicht der Basis
- offset_x/y sind relativ zum Parent-Face-Zentrum

## Beispiel
Basis 100x80x15, Steg 10x40x20 bündig rechts-hinten auf Basis:
```json
"placement": {
  "face": ">Z",
  "position": "offset",
  "offset_x": 45,
  "offset_y": 20
}
```
Berechnung: offset_x = 100/2 - 10/2 = 45 (bündig rechts)
             offset_y = 80/2 - 40/2 = 20 (bündig hinten)
