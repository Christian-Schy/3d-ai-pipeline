# Interpreter — When to Ask, When to Proceed

## Complete Specifications (no questions needed)
- "30mm cube with 8mm hole on top, centered, through-hole" → complete
- "60x40x8mm mounting plate, M4 corner holes 5mm from edge, M10 center hole" → complete
- "L-bracket 40x40x4mm, 60mm long, 5mm mounting holes on both flanges" → complete
- "30mm Würfel, oben rechts eine Platte 10x30x50mm" → complete (all 3 dimensions given: 10=thickness/X, 30=length/Y, 50=height/Z)
- "Würfel mit extrudierter Platte auf der rechten Seite, 10mm dick, 30mm lang, 50mm hoch" → complete
- "Cube with plate attached to right face, 10x30x50mm" → complete

### Key rule: Three numbers given for a plate/box = ALL dimensions present, do NOT ask
If user gives 3 dimensions (e.g. "10x30x50mm") for a named shape (Platte/plate/box), the spec is complete.
Map them as: first=X-thickness (depth from face), second=Y-length, third=Z-height (or by context).

## Incomplete — Ask These Questions

### Missing dimensions
User: "a box with a hole"
Ask: "What are the dimensions of the box (length x width x height in mm)?"
Ask: "What is the hole diameter, and where is it positioned?"

### Ambiguous hole position
User: "a plate with holes"
Ask: "How many holes, what diameter, and where should they be positioned?"

### Missing wall thickness (for hollow parts)
User: "a hollow box"
Ask: "What should the wall thickness be in mm?"

### Ambiguous 'hole' (through vs blind)
User: "a cube with a hole on top"
Ask: "Should the hole go all the way through, or only partway (blind hole)? If blind, how deep?"

## What NOT to Ask
- Do not ask about material (CadQuery generates geometry only)
- Do not ask about color or surface finish
- Do not ask about assembly or fasteners beyond geometry
- Do not ask for clarification on standard sizes (M3=3mm, M4=4mm, M5=5mm)

## Würfel mit extrudierter Platte — Cube with Extruded Plate

User: "30mm Würfel, oben soll vom Würfel eine Platte extrudiert werden auf der rechten Seite 10x30x50mm"
User: "ein Würfel 30mm, oben rechts eine Platte 10 dick 30 lang 50 hoch"
User: "cube 30mm, on top right side a plate extruded 10x30x50mm"

This is ADDITIVE geometry (Union). The plate is a solid box added ON TOP of the cube.
"oben" (top) = plate sits on the top face (+Z), extends upward.
"rechte Seite" (right side) = plate is positioned at the right (+X) edge of the top face, flush with the cube's right face. NOT on the right face itself.

Correct Spec:
"30mm cube (30x30x30mm). On the top face (+Z), a solid plate 10mm wide (X) x 30mm long (Y) x 50mm tall (Z), positioned flush with the right (+X) face. Plate sits on top of the cube and extends upward. Union operation."

WRONG: "plate on the right face (+X), centered vertically" — plate sticks sideways, wrong.
CORRECT: "plate on the top face (+Z), flush with right (+X) edge" — plate extends upward, right edge aligned.

Position for planner: plate.x = cube_x/2 - plate_x/2, plate.z = cube_z/2 + plate_z/2.
Example: 30mm cube + 10mm plate → plate.x = 15 - 5 = 10, plate.z = 15 + 25 = 40.

## Additive vs. Subtractive Operations — CRITICAL DISTINCTION

**ADDITIVE** (adds material — Union):
- "Platte auf der rechten Seite" = a solid plate attached to the right face → Union
- "Angebaut", "extrudiert", "aufgesetzt", "hinzugefügt" = add solid material
- "30mm Würfel, oben rechts eine 10x30x50mm Platte" → cube PLUS plate (Union of two boxes)

**SUBTRACTIVE** (removes material — Cut):
- "Bohrung", "Loch", "Nut", "Schlitz", "Vertiefung", "eingelassen" = remove material
- "Tasche", "Aussparung" = pocket / cutout

IMPORTANT: "Platte extrudiert" = **solid plate added** (Union). NOT a slot/cut.
IMPORTANT: "oben auf der rechten Seite" = plate ON THE TOP FACE, flush with the right (+X) edge — NOT on the right face.

Example — additive (plate on top, at right edge):
User: "30mm Würfel oben soll eine Platte extrudiert werden auf der rechten Seite 10x30x50mm"
Correct Spec: "30mm cube (30x30x30mm). On the top face (+Z), a solid plate 10mm wide (X) x 30mm long (Y) x 50mm tall (Z), flush with the right (+X) face of the cube. Plate sits on top of the cube, extends upward."

WRONG interpretation: "plate on the right face (+X), centered vertically" → this makes the plate stick sideways.
CORRECT interpretation: "plate on the top face (+Z), positioned at the right (+X) edge" → plate extends upward.

Position hint for planner: plate.x = cube_x/2 - plate_x/2 = 15 - 5 = 10, plate.z = cube_z/2 + plate_z/2 = 15 + 25 = 40.

## German → English Term Translations
Always translate these German terms into their standard English geometry counterparts:
- "Phase" / "Fase" / "Anfasung" → **chamfer** (angled cut at 45° along an edge)
- "Verrundung" / "Abrundung" / "Rundung" → **fillet** (rounded edge, given by radius)
- "Bohrung" / "Loch" → hole
- "Nut" / "Schlitz" / "Kanal" → slot or groove
- "Würfel" → cube / box
- "Zylinder" → cylinder
- "Platte" / "Anbauplatte" → plate (solid box, additive)
- "extrudiert" / "angebaut" / "aufgesetzt" → attached / added (Union, additive)

IMPORTANT: "Phase" means chamfer — an angled flat cut. Do NOT describe it as "rectangular cutout."
Example: "2mm Phase an allen Kanten" → "2mm chamfer on all edges"

## Specification Format
Write as one clear paragraph:
"[Shape] [dimensions]mm. [Feature 1]: [details]. [Feature 2]: [details]. [Finish]: [fillet/chamfer if any]."

Example:
"Rectangular plate 60x40x8mm, solid. Four M4 through-holes (diameter 4mm) at corners,
positioned 5mm from each edge. Central M10 through-hole (diameter 10mm). No fillets."

Example with chamfer:
"30mm cube, solid. 2mm chamfer on all edges."

Example with fillet:
"30mm cube, solid. 2mm fillet radius on all edges."
