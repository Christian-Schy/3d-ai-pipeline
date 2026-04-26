# Offset-Formeln — Kantenabstand, Bündig, Zentriert
Tags: offset, abstand, kante, rand, bündig, flush, centered, berechnung

## Koordinatensystem

Box mit centered=(True, True, False):
- X-Achse: [-W/2 .. +W/2] (links nach rechts)
- Y-Achse: [-L/2 .. +L/2] (vorne nach hinten)
- Z-Achse: [0 .. H] (unten nach oben)

## Face-abhängige Achsen

Auf welcher Face sitzt das Feature? Das bestimmt welche Parent-Dimension
für offset_x und offset_y gilt:

| Face | offset_x entlang | offset_y entlang |
|------|------------------|------------------|
| >Z / <Z | Parent.x | Parent.y |
| >X / <X | Parent.y | Parent.z |
| >Y / <Y | Parent.x | Parent.z |

## Zentriert
offset_x = 0, offset_y = 0

## Bündig (flush)

flush_right:        offset_x = +(Parent_W/2 - Child_W/2)
flush_left:         offset_x = -(Parent_W/2 - Child_W/2)
flush_top (hinten): offset_y = +(Parent_L/2 - Child_L/2)
flush_bottom (vorne): offset_y = -(Parent_L/2 - Child_L/2)

Kombination: flush_right_top = beide Formeln gleichzeitig

W und L sind die face-abhängigen Dimensionen (siehe Tabelle oben).

## Kantenabstand ("Xmm von Kante")

"Xmm von rechter Kante":  offset_x = +(Dim/2 - X)
"Xmm von linker Kante":   offset_x = -(Dim/2 - X)
"Xmm von Oberkante":      offset_y = +(Dim/2 - X)
"Xmm von Unterkante":     offset_y = -(Dim/2 - X)

Dim = face-abhängige Parent-Dimension für diese Achse.

### Beispiel 1: >Z Face — Bohrung auf 50mm Würfel
"Bohrung 20mm von rechter Kante, 10mm von Unterkante" auf >Z Face:
- >Z Face: offset_x entlang Parent.x (=50), offset_y entlang Parent.y (=50)
- "20mm von rechter Kante": offset_x = +(50/2 - 20) = +5.0
- "10mm von Unterkante":    offset_y = -(50/2 - 10) = -15.0

### Beispiel 2: >X Face — Bohrung auf rechter Seite eines 50×50×50 Würfels
"rechts eine Bohrung, 10mm von Oberkante, 20mm von rechter Kante"
- Face = >X (rechte Seite)
- >X Face: offset_x entlang Parent.y (=50), offset_y entlang Parent.z (=50)
- "10mm von Oberkante" = 10mm von oberer Kante der >X Face → offset_y = +(50/2 - 10) = +15.0
- "20mm von rechter Kante" = 20mm von rechter Kante der >X Face → offset_x = +(50/2 - 20) = +5.0
→ offset_x=5.0, offset_y=15.0

★★★ WICHTIG: Offset ist NICHT der Rohdistanzwert!
  "10mm von Kante" bei Dim=50 → offset = ±(50/2 - 10) = ±15  (NICHT ±10!)
  "20mm von Kante" bei Dim=50 → offset = ±(50/2 - 20) = ±5   (NICHT ±20!)
  Die Formel ist IMMER: offset = ±(Dim/2 - Abstand)

### Beispiel 3: <X Face — Bohrung auf linker Seite
"links eine Bohrung, 15mm von Unterkante, 10mm von vorderer Kante"
- Face = <X (linke Seite)
- <X Face: offset_x entlang Parent.y (=50), offset_y entlang Parent.z (=50)
- "15mm von Unterkante" → offset_y = -(50/2 - 15) = -10.0
- "10mm von vorderer Kante" → offset_x = -(50/2 - 10) = -15.0
→ offset_x=-15.0, offset_y=-10.0

### Beispiel 4: Symmetrischer Inset
"Bohrung oben rechts, 20mm von den Kanten" auf >Z Face eines 50mm Würfels:
- offset_x = +(50/2 - 20) = +5.0
- offset_y = +(50/2 - 20) = +5.0

★ "von den Kanten" = symmetrischer Inset, Vorzeichen aus Position (oben rechts = +/+)

## "von unten/oben Xmm" als Positionsangabe

ACHTUNG: "von unten 10mm entfernt" kann bedeuten:
1. Face-Richtung: Bohrung VON der Unterseite → face="<Z"
2. Positionsangabe: 10mm von der Unterkante entfernt → offset_y = -(Dim/2 - 10)

Kontext entscheidet:
- "Bohrung von unten" → Face-Richtung (<Z)
- "10mm von unten entfernt" nach einer Face-Angabe → Positionsangabe

## Bohrungen mit Kantenabstand
"Xmm vom Rand" bei Eckbohrungen:
  → offset_x = ±(Parent_W/2 - X)
  → offset_y = ±(Parent_L/2 - X)
  Vorzeichen: + für rechts/hinten, - für links/vorne
