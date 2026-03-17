# Planner Examples — primitive_single / simple shapes

## Solid Box
```json
{
  "description": "30x20x10mm solid box",
  "root": {"type": "box", "x": 30, "y": 20, "z": 10,
           "position": {"x": 0, "y": 0, "z": 0}}
}
```

## Solid Cylinder
```json
{
  "description": "50mm tall, 20mm diameter cylinder",
  "root": {"type": "cylinder", "radius": 10.0, "height": 50,
           "position": {"x": 0, "y": 0, "z": 0}}
}
```

## Hollow Box (Shell / Enclosure)
```json
{
  "description": "80x60x40mm enclosure box, 2mm walls, open top",
  "root": {
    "type": "shell",
    "thickness": 2.0,
    "open_face": ">Z",
    "child": {"type": "box", "x": 80, "y": 60, "z": 40,
              "position": {"x": 0, "y": 0, "z": 0}}
  }
}
```
Rule: shell wraps a single primitive — it is never nested inside cut/union.
Rule: open_face uses CadQuery selector syntax (">Z" = top face, ">X" = right face).

## Stacked Cylinders (Drehteil / Stepped Rotational Part)

**CRITICAL STACKING FORMULA** — cylinders must touch with NO GAP:
  total_height = h1 + h2 + h3 + ...
  bottom = -total_height / 2
  z_center_1 = bottom + h1/2
  z_center_2 = bottom + h1 + h2/2
  z_center_3 = bottom + h1 + h2 + h3/2

Example: Ø20×10mm + Ø30×20mm + Ø20×40mm → total=70mm, bottom=-35
  z1 = -35 + 5  = -30   (top = -30+5 = -25)
  z2 = -35 + 10 + 10 = -15  (bottom = -15-10 = -25 ✓ touches z1 top)
  z3 = -35 + 10 + 20 + 20 = 15  (bottom = 15-20 = -5 = z2 top ✓)

```json
{
  "description": "Stepped rotational part: Ø20×10mm + Ø30×20mm + Ø20×40mm stacked",
  "root": {
    "type": "union",
    "target": {
      "type": "union",
      "target": {"type": "cylinder", "radius": 10.0, "height": 10, "position": {"x": 0, "y": 0, "z": -30}},
      "tool":   {"type": "cylinder", "radius": 15.0, "height": 20, "position": {"x": 0, "y": 0, "z": -15}}
    },
    "tool": {"type": "cylinder", "radius": 10.0, "height": 40, "position": {"x": 0, "y": 0, "z": 15}}
  }
}
```
Rule: ALWAYS verify adjacent cylinders touch: upper_z - upper_h/2 == lower_z + lower_h/2

## CSG Schema Rules (apply to all blueprints)
- position (x,y,z) is always the CENTER of the shape
- union/cut ONLY have "target" and "tool" — never "children" or "positions"
- fillet/chamfer nodes are ALWAYS the outermost node (last operation)
