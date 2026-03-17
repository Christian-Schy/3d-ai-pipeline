# Planner Examples — modification (fillet, chamfer, resize, reposition, rotational parts)

## Stepped Rotational Part (Drehteil / Stufenwelle)

**STACKING FORMULA — cylinders MUST touch, no gaps:**
  total = h1 + h2 + h3,  bottom = -total/2
  z1 = bottom + h1/2
  z2 = bottom + h1 + h2/2
  z3 = bottom + h1 + h2 + h3/2

Example: Ø20×10 + Ø30×20 + Ø20×40 → total=70, bottom=-35
  z1 = -35 + 5 = **-30**,  z2 = -35 + 10 + 10 = **-15**,  z3 = -35 + 10 + 20 + 20 = **15**

```json
{
  "description": "Stepped shaft: Ø20×10mm + Ø30×20mm + Ø20×40mm stacked",
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
Verify: cyl1 top = -30+5 = -25, cyl2 bottom = -15-10 = -25 ✓ | cyl2 top = -15+10 = -5, cyl3 bottom = 15-20 = -5 ✓

Rule: fillet/chamfer is ALWAYS the outermost (last) node — applied after all cuts/unions.
Rule: edges selector: "|Z" = vertical edges, "|X" = edges parallel to X, ">Z" = top face edges.
Rule: fillet radius must be smaller than the thinnest wall (typically ≤ thickness/2).

## Box with Fillet on Vertical Edges
```json
{
  "description": "30mm cube with 2mm fillet on all vertical edges",
  "root": {
    "type": "fillet",
    "radius": 2.0,
    "edges": "|Z",
    "child": {"type": "box", "x": 30, "y": 30, "z": 30,
              "position": {"x": 0, "y": 0, "z": 0}}
  }
}
```

## Box with Chamfer on Top Edges
```json
{
  "description": "40x30x15mm block with 1.5mm chamfer on top face edges",
  "root": {
    "type": "chamfer",
    "distance": 1.5,
    "edges": ">Z",
    "child": {"type": "box", "x": 40, "y": 30, "z": 15,
              "position": {"x": 0, "y": 0, "z": 0}}
  }
}
```

## Fillet Applied After Cut (hole in filleted box)
```json
{
  "description": "50mm cube with 10mm hole and 3mm fillet on all vertical edges",
  "root": {
    "type": "fillet",
    "radius": 3.0,
    "edges": "|Z",
    "child": {
      "type": "cut",
      "target": {"type": "box", "x": 50, "y": 50, "z": 50,
                 "position": {"x": 0, "y": 0, "z": 0}},
      "tool":   {"type": "cylinder", "radius": 5.0, "height": 54,
                 "position": {"x": 0, "y": 0, "z": 0}}
    }
  }
}
```
Rule: fillet wraps the ENTIRE cut result — it is the root node.
