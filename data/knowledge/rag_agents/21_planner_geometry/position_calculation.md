# Position Calculation — ★ Bündig/Zentriert/Versetzt berechnen
Tags: position, berechnen, bündig, zentriert, versetzt, offset, flush

## Grundregel
Basis: box(W, L, H, centered=(True, True, False))
→ Basis belegt: X [-W/2 .. +W/2], Y [-L/2 .. +L/2], Z [0 .. H]
→ Basis-Top-Face: Z = H
→ Basis-Center auf Top: (0, 0, H)

## Feature-Positionierung auf Basis-Oberseite

Feature: box(fw, fl, fh) soll auf die Basis:

### Zentriert
translate_x = 0
translate_y = 0
translate_z = H + fh/2

### Bündig rechts
translate_x = W/2 - fw/2
translate_z = H + fh/2

### Bündig links
translate_x = -(W/2 - fw/2)
translate_z = H + fh/2

### Bündig hinten
translate_y = L/2 - fl/2
translate_z = H + fh/2

### Bündig vorne
translate_y = -(L/2 - fl/2)
translate_z = H + fh/2

### Ecke rechts-hinten
translate_x = W/2 - fw/2
translate_y = L/2 - fl/2
translate_z = H + fh/2

### Versetzt um Abstand d vom Rand
translate_x = W/2 - fw/2 - d  (rechts, d mm vom Rand)

### ★ Kantenabstand für Bohrungen/Features — "X mm von Kante"
"Feature-Zentrum X mm von Kante entfernt" (NICHT offset = X!):
offset_y = -(L/2 - X)   für −Y Kante (Unterkante)
offset_y = +(L/2 - X)   für +Y Kante (Oberkante)
offset_x = -(W/2 - X)   für −X Kante (links)
offset_x = +(W/2 - X)   für +X Kante (rechts)

Beispiel: Basis 30×30, Bohrung ∅10, "10mm von Unterkante (-Y)":
  offset_y = -(30/2 - 10) = -(15-10) = -5.0 ✓
  FALSCH: offset_y = -10.0 → Zentrum bei Y=-10, nur 5mm von Y=-15 Kante!

## Z-Stacking (Features übereinander)
Feature 1: h1 auf Basis H → Z1 = H + h1/2 → Top1 = H + h1
Feature 2: h2 auf Feature 1 → Z2 = H + h1 + h2/2 → Top2 = H + h1 + h2

## Bohrung-Position relativ zum Parent
Bohrung auf Parent-Oberseite:
- Zentriert: offset_x = 0, offset_y = 0
- Am Rand: offset_x = parent_w/2 - inset
- In Ecken: offset_x = ±(parent_w/2 - inset), offset_y = ±(parent_l/2 - inset)

## Lochkreis-Berechnung
circle_diameter = Teilkreisdurchmesser (User-Angabe)
hole_positions = [(r·cos(i·360/n), r·sin(i·360/n)) für i in 0..n-1]
wobei r = circle_diameter / 2

★ HÄUFIGSTER FEHLER: Radius und Durchmesser verwechseln!

## Prüfung: Passt Feature auf Parent?
- Feature-Breite ≤ Parent-Breite
- Feature-Länge ≤ Parent-Länge
- Bohrung: hole_diameter < min(parent_w, parent_l)
- Lochkreis: circle_diameter/2 + hole_diameter/2 < min(parent_w, parent_l)/2
- Eckbohrung: inset > hole_diameter/2
