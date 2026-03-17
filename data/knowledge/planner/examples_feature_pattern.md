# Planner Examples — feature_pattern (arrays, multiple holes, grids)

Rule: union has ONLY "target" and "tool" — NEVER "children" or "positions" array.
Rule: For N holes as tool: chain (N-1) union nodes.
Rule: corner offset formula = side/2 - edge_distance.
     Example: 60mm plate, 5mm from edge → offset = 60/2 - 5 = 25mm.

## Plate with Four Corner Holes (M4, 4mm dia, 5mm from corners)
```json
{
  "description": "60x40x8mm plate with M4 corner holes (4mm dia, 5mm from corners)",
  "root": {
    "type": "cut",
    "target": {"type": "box", "x": 60, "y": 40, "z": 8,
               "position": {"x": 0, "y": 0, "z": 0}},
    "tool": {
      "type": "union",
      "target": {"type": "cylinder", "radius": 2.0, "height": 10, "position": {"x":  25, "y":  15, "z": 0}},
      "tool": {
        "type": "union",
        "target": {"type": "cylinder", "radius": 2.0, "height": 10, "position": {"x": -25, "y":  15, "z": 0}},
        "tool": {
          "type": "union",
          "target": {"type": "cylinder", "radius": 2.0, "height": 10, "position": {"x":  25, "y": -15, "z": 0}},
          "tool":   {"type": "cylinder", "radius": 2.0, "height": 10, "position": {"x": -25, "y": -15, "z": 0}}
        }
      }
    }
  }
}
```
Positions: x = ±(60/2 - 5) = ±25, y = ±(40/2 - 5) = ±15.

## Plate with Two Holes on Center Line
```json
{
  "description": "100x30x5mm plate with two 5mm holes, 20mm from each end",
  "root": {
    "type": "cut",
    "target": {"type": "box", "x": 100, "y": 30, "z": 5,
               "position": {"x": 0, "y": 0, "z": 0}},
    "tool": {
      "type": "union",
      "target": {"type": "cylinder", "radius": 2.5, "height": 8, "position": {"x":  30, "y": 0, "z": 0}},
      "tool":   {"type": "cylinder", "radius": 2.5, "height": 8, "position": {"x": -30, "y": 0, "z": 0}}
    }
  }
}
```
Rule: offset from end = -(solid_x/2 - distance) = -(50 - 20) = -30 (and +30).
Rule: 2 holes need 1 union node. 3 holes need 2 union nodes. 4 holes need 3.
