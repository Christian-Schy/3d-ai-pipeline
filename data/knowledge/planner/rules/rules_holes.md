# Bohrungsregeln

## Bohrungstypen
- Durchgangsbohrung: depth=null (nicht depth=0!)
- Sackbohrung: depth=expliziter Wert in mm (z.B. depth=10.0)
- Stufenbohrung (Counterbore): type="cbore_hole", cbore_diameter, cbore_depth
- Kegelsenk (Countersink): type="csk_hole", csk_angle=90

## Positionierung
- Auf Top-Face: face=">Z", offset_x/y = Abstand von Flächenmitte
- Zentriert: offset_x=0, offset_y=0
- Mehrere Löcher: IMMER hole_pattern_grid oder hole_pattern_circular verwenden — nie einzelne Bohrungen für Muster!

### ★ Kantenabstand → Offset umrechnen
"Xmm von Kante entfernt" = Feature-Zentrum X mm von der Kante.
Basis box(W, L, H, centered=(True,True,False)):
- "von Unterkante (-Y) Xmm": offset_y = -(L/2 - X)
- "von Oberkante (+Y) Xmm": offset_y = +(L/2 - X)
- "von rechts (+X) Xmm": offset_x = +(W/2 - X)
- "von links (-X) Xmm": offset_x = -(W/2 - X)

Beispiel: Würfel 30mm, Bohrung ∅10, "10mm von Unterkante":
offset_y = -(30/2 - 10) = -5.0  ← RICHTIG
offset_y = -10.0                ← FALSCH (nur 5mm von Kante, Bohrung r=5 ragt über Rand!)

## ★ Seitenbohrungen — Bohrung NICHT von oben
Die Bohrung geht IN RICHTUNG der Face-Normalen. Face bestimmt Bohrrichtung!
- "parallel zur X-Achse" / "in X-Richtung" → face=">X" oder "<X" (Bohrachse ∥ X)
- "parallel zur Y-Achse" / "in Y-Richtung" → face=">Y" oder "<Y" (Bohrachse ∥ Y)
- "parallel zur Z-Achse" / "von oben/unten"  → face=">Z" oder "<Z" (Bohrachse ∥ Z)
- "durch die Dicke" → Face senkrecht zur dünnsten Dimension
- "von der Seite" / "seitlich" → Face aus Kontext ableiten

★ ESELSBRÜCKE: face=">X" → Bohrachse ∥ X. Der Buchstabe im Face = Bohrachse!

- ★ Auf Seitenflächen: offset_x und offset_y beziehen sich auf die Workplane-Achsen der Fläche!
  - Auf >X/<X Fläche: offset_x = Y-Position, offset_y = Z-Position
  - Auf >Y/<Y Fläche: offset_x = X-Position, offset_y = Z-Position
- "25mm von Oberkante" auf Seitenfläche → offset_y = +(Parent_Z/2 - 25)

## Wandstärke
- Mindest-Wandstärke: 2mm
- Bohrung_durchmesser < (Material_breite - 4mm)
- Bei Lochkreis: circle_r + hole_r < parent_r

## Häufige Fehler
- depth=0 statt depth=null für Durchgangsbohrung
- Bohrung tiefer als Material → depth MUSS ≤ parent.z sein
- Zu großer Durchmesser → Wandstärke prüfen
