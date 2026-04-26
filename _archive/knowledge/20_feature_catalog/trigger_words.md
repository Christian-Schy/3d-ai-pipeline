# Trigger Words — Welche Worte → welcher Feature-Typ
Tags: trigger, erkennung, wort, mapping, keywords

## Deutsch → Feature-Typ

### Grundkörper
Platte, Block, Quader, Würfel → `base_plate`
Zylinder, Welle, Rohr, Scheibe, Nabe → `base_cylinder`
Kugel → `base_sphere`

### Additive
Steg, Rippe, Leiste, Erhöhung → `extrusion_rect`
Boss, Nocke, Zapfen, Buchse, Flansch → `extrusion_round`
Stufe, Absatz → `step`

### Subtraktive
Bohrung, Loch, bohren → `hole_single`
Durchgangsbohrung, durchgehendes Loch → `hole_single` (depth=null)
Sackloch, Sackbohrung → `hole_single` (depth=Zahl)
Stufenbohrung, Senkbohrung, Innensechskant → `hole_counterbore`
Kegelsenkung, Senkkopf → `hole_countersink`
Tasche, Vertiefung, Einsenkung → `pocket_rect`
Nut, Slot, Langloch → `slot`
Aussparung, Ausschnitt, Fenster → `cutout`

### Muster
Lochraster, Lochbild, Reihe von Löchern → `hole_pattern_grid`
Lochkreis, Teilkreis, Flanschbohrungen, Löcher auf Kreis → `hole_pattern_circular`
Muster, wiederholen, Array → `pattern_linear` oder `pattern_polar`
spiegeln, symmetrisch → `pattern_mirror`

### Modifikationen
Verrundung, abrunden, Radius an Kante → `fillet`
Fase, anfasen, 45° → `chamfer`
aushöhlen, dünnwandig, Gehäuse → `shell`

### Komplex
drehen, Drehkörper, Revolution → `revolve`
entlang Pfad, Sweep → `sweep`
Übergang, Loft → `loft`
Gewinde → `thread`
Zahnrad → `gear`

## Mehrfach-Erkennung
Ein Satz kann MEHRERE Features enthalten:
"Platte mit Lochkreis und Steg" → [`base_plate`, `hole_pattern_circular`, `extrusion_rect`]
