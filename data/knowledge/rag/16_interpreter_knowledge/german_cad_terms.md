# German CAD Terms — Deutsche Fachbegriffe → Feature-Typen
Tags: deutsch, german, fachbegriff, übersetzung, mapping, interpreter

## Wann verwenden
- Interpreter muss deutsche Beschreibungen in Feature-Typen umwandeln
- Feature Tagger muss deutsche Begriffe erkennen

## Mapping-Tabelle

### Grundkörper
| Deutsch | Feature-Typ | CadQuery |
|---------|-------------|----------|
| Platte, Platte | base_plate / box | .box() |
| Block, Quader | box | .box() |
| Würfel | box (gleiche Seiten) | .box(a, a, a) |
| Zylinder, Welle | cylinder | .cylinder() |
| Kugel | sphere | .sphere() |
| Kegel, Konus | cone | .cone() |
| Ring, Torus | torus | .torus() |

### Additive Features
| Deutsch | Feature-Typ | CadQuery |
|---------|-------------|----------|
| Steg, Rippe | extrusion_rectangular | .rect().extrude() |
| Aufsatz, Boss, Nocke | boss_cylindrical / boss_rectangular | .circle().extrude() / .rect().extrude() |
| Flansch | extrusion_cylindrical | .circle().extrude() |
| Absatz, Stufe | step (box on face) | .box() + .union() |
| Erhöhung | extrusion | .extrude() |

### Subtraktive Features
| Deutsch | Feature-Typ | CadQuery |
|---------|-------------|----------|
| Bohrung, Loch | hole_single | .hole() |
| Durchgangsbohrung | hole_through | .hole(d) (kein depth) |
| Sackloch, Sackbohrung | hole_blind | .hole(d, depth) |
| Senkbohrung, Stufenbohrung | hole_counterbore | .cboreHole() |
| Kegelsenkung | hole_countersink | .cskHole() |
| Tasche, Vertiefung | pocket_rectangular | .rect().cutBlind() |
| Nut, Slot | groove / slot | .rect().cutBlind() / .slot2D().cutThruAll() |
| Nut entlang der X/Y-Achse | slot (volle Breite!) | length = VOLLE Dimension des Parents in dieser Richtung |
| Langloch | slot_through | .slot2D().cutThruAll() |
| Aussparung, Ausschnitt | cutout | .rect().cutThruAll() |
| Fase | chamfer | .chamfer() |
| Verrundung, Abrundung, Radius | fillet | .fillet() |

### Muster
| Deutsch | Feature-Typ | CadQuery |
|---------|-------------|----------|
| Lochkreis, Teilkreis | bolt_circle / hole_pattern_circular | .polarArray() / .pushPoints() |
| Lochraster, Lochbild | hole_pattern_grid | .rArray() |
| Muster, Pattern | linear_pattern / polar_pattern | .rArray() / .polarArray() |
| Spiegeln | mirror | .mirror() |

### Positionierung
| Deutsch | Bedeutung | Mapping |
|---------|-----------|---------|
| oben | +Z (Oberseite) | face: ">Z" |
| unten | -Z (Unterseite) | face: "<Z" |
| rechts | +X | face: ">X" / offset_x: positiv |
| links | -X | face: "<X" / offset_x: negativ |
| vorne | -Y (kleinstes Y) | face: "<Y" |
| hinten | +Y (größtes Y) | face: ">Y" |
| mittig, zentriert | (0, 0) | offset: 0, 0 |
| bündig | am Rand | offset: ±(parent/2 - feature/2) |
| darin, im | im Parent-Feature | NearestToPointSelector auf Parent |
| darauf, drauf | auf der Oberseite des Parent | face: ">Z" des Parent |
| daneben | neben dem Feature | offset von Feature-Position |
| seitlich | auf Seitenfläche | face: ">X", "<X", ">Y", "<Y" |
| durchgehend | komplett durch | depth: None / cutThruAll |

### Mehrdeutige Begriffe
| Deutsch | Könnte bedeuten | Klärung nötig? |
|---------|----------------|----------------|
| "Platte drauf" | Extrusion ODER separates Teil | Ja — bündig? Zentriert? |
| "Loch" | Durchgang ODER Sackloch | Ja — Tiefe? |
| "abgerundet" | Fillet ODER Chamfer | Ja — Radius oder 45°? |
| "Rand" | Kante ODER Fläche am Rand | Nein — meist Kante |
