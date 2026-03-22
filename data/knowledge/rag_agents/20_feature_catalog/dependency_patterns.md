# Dependency Patterns — Typische Parent-Child-Beziehungen
Tags: dependency, parent, child, beziehung, hierarchie

## Regeln

1. JEDES Feature hat genau EINEN Parent (außer base)
2. Base-Features haben Parent = null
3. Child muss NACH Parent gebaut werden
4. Subtraktive Features können auf additiven Features sitzen

## Typische Beziehungen

| Child-Typ | Typischer Parent | Placement |
|-----------|-----------------|-----------|
| `extrusion_rect` | `base_plate` | top/side + Position |
| `extrusion_round` | `base_plate` | top + Position |
| `hole_single` | `base_plate` ODER `extrusion_*` | face + center/offset |
| `hole_pattern_grid` | `base_plate` | top + center |
| `hole_pattern_circular` | `base_plate` ODER `extrusion_round` | top + center |
| `pocket_rect` | `base_plate` | top + Position |
| `slot` | `base_plate` | top/side |
| `fillet` | letztes Feature | Kanten |
| `chamfer` | letztes Feature | Kanten |

## Erkennung aus Text

"darin", "im" → Child sitzt AUF/IN dem zuletzt genannten Feature
"darauf", "drauf" → Child sitzt auf der Oberseite des genannten Features
"daneben", "neben" → Child sitzt auf GLEICHER Basis wie das genannte Feature
"auf der Platte" → Parent = base
"im Steg" → Parent = der Steg (extrusion)

## Beispiel
Input: "Platte 100x100x20, rechts ein Steg 10x100x20, im Steg eine Bohrung ∅10"
→ base (base_plate) → steg (extrusion_rect, parent=base) → bohrung (hole_single, parent=steg)
