# Feature-Typen — Katalog, Trigger-Wörter, Klassifikation
Tags: feature, typ, katalog, trigger, erkennung, klassifikation

## Grundkörper (ROOT, parent=null)

| Typ | Trigger-Wörter |
|-----|----------------|
| box / base_plate | Platte, Block, Quader, Würfel |
| base_cylinder | Zylinder, Welle, Rohr, Scheibe, Nabe |
| base_sphere | Kugel |

## Additive Features (operation="add")

| Typ | Trigger-Wörter |
|-----|----------------|
| extrusion_rect | Aufsatz, Steg, Rippe, Leiste, Erhöhung |
| extrusion_round | Boss, Nocke, Zapfen, Buchse, Flansch |
| step | Stufe, Absatz |

## Subtraktive Features (operation="subtract")

| Typ | Trigger-Wörter |
|-----|----------------|
| hole_single | Bohrung, Loch (einzeln) |
| hole_counterbore | Stufenbohrung, Senkbohrung, Innensechskant |
| hole_countersink | Kegelsenkung, Senkkopf |
| slot / groove | Nut, Rille, Langloch |
| pocket_rect / cutout | Tasche, Vertiefung, Aussparung |

## Muster (operation="subtract", IMMER konsolidieren!)

| Typ | Trigger-Wörter |
|-----|----------------|
| hole_pattern_grid | "in jede Ecke", "Eckbohrungen", "4 Bohrungen am Rand" |
| hole_pattern_circular | "Lochkreis", "Teilkreis", "Bohrungen auf einem Kreis" |
| hole_pattern_linear | "in einer Reihe", "im Abstand von Xmm", "gleichmäßig verteilt" |

★ NIEMALS ein Muster in einzelne hole_single aufteilen!
  "4 Eckbohrungen" = EIN hole_pattern_grid (NICHT 4× hole_single!)

## Modifikationen (operation="modify")

| Typ | Trigger-Wörter |
|-----|----------------|
| fillet | Verrundung, abrunden, Radius an Kante |
| chamfer | Fase, anfasen, 45° |
| shell | aushöhlen, dünnwandig, Gehäuse |

## Komplexe Features (für Spezialisten)

| Typ | Trigger-Wörter |
|-----|----------------|
| angled_extrusion | "im Winkel", "schräg extrudiert", "30°" |
| arc_cut | Bogenausschnitt |
| triangle_cut | Dreieckausschnitt |
| custom_shape_cut/add | beliebige 2D-Form |
| loft / sweep / revolution | Übergang, Pfad-Extrusion, Drehkörper |

## Klassifikationsregel

Wähle den SPEZIFISCHSTEN Typ:
- "Lochkreis" → hole_pattern_circular (nicht hole_single)
- "Boss auf Platte" → extrusion_round (nicht base_cylinder)
- "4 Bohrungen in einer Reihe" → hole_pattern_linear (nicht 4× hole_single)
- "schräge Platte 30°" → angled_extrusion (nicht extrusion_rect)
