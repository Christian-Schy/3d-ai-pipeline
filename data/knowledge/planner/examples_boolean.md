# Planner Examples — primitive_composite / boolean operations

Rule: union has ONLY "target" and "tool" — NEVER "children" array.
Rule: cut  has ONLY "target" and "tool" — NEVER "positions" array.
Rule: For N shapes joined: chain (N-1) union nodes, each wrapping the next.

## L-Bracket (two boxes joined with union)
```json
{
  "description": "L-bracket 40x40x4mm profile, 60mm long",
  "root": {
    "type": "union",
    "target": {"type": "box", "x": 40, "y": 4,  "z": 60, "position": {"x": 0,   "y": 0,  "z": 0}},
    "tool":   {"type": "box", "x": 4,  "y": 40, "z": 60, "position": {"x": -18, "y": 18, "z": 0}}
  }
}
```
Rule: position offset = (dim_a/2 + dim_b/2) → here (40/2 + 4/2) = 22, centered → -18/+18.

## T-Profile (three parts chained with union)
```json
{
  "description": "T-profile: 60x5x40mm vertical web, 40x5x40mm horizontal flange",
  "root": {
    "type": "union",
    "target": {"type": "box", "x": 60, "y": 5, "z": 40, "position": {"x": 0,   "y": 0,    "z": 0}},
    "tool":   {"type": "box", "x": 5,  "y": 40, "z": 40, "position": {"x": 0,  "y": 22.5, "z": 0}}
  }
}
```

## Box with Material Removed (blind pocket with cut)
```json
{
  "description": "50x50x20mm block with 30x30x10mm pocket on top",
  "root": {
    "type": "cut",
    "target": {"type": "box", "x": 50, "y": 50, "z": 20, "position": {"x": 0, "y": 0, "z": 0}},
    "tool":   {"type": "box", "x": 30, "y": 30, "z": 10, "position": {"x": 0, "y": 0, "z": 5}}
  }
}
```
Rule: tool position.z = solid_height/2 - pocket_depth/2 → keeps pocket flush with top.

## CSG Schema Rules
- For 3 shapes: 2 union nodes. For 4 shapes: 3 union nodes. Always chain.
- position (x,y,z) is the CENTER of the shape, not corner.
