# Planner Examples — feature_additive (boss, rib, peg, raised geometry)

Rule: additive features use union — target = base solid, tool = added feature.
Rule: tool position.z = solid_height/2 + feature_height/2 (sits ON TOP of base).
Rule: for features on side faces, adjust x or y offset accordingly.

## Box with Central Boss (raised cylinder on top)
```json
{
  "description": "50x50x10mm plate with 12mm diameter, 8mm tall boss on top center",
  "root": {
    "type": "union",
    "target": {"type": "box", "x": 50, "y": 50, "z": 10,
               "position": {"x": 0, "y": 0, "z": 0}},
    "tool":   {"type": "cylinder", "radius": 6.0, "height": 8,
               "position": {"x": 0, "y": 0, "z": 9}}
  }
}
```
Rule: boss position.z = solid_height/2 + boss_height/2 = 5 + 4 = 9.

## Box with Rectangular Rib (stiffener on side)
```json
{
  "description": "80x40x20mm block with 5x5x40mm rib along front face center",
  "root": {
    "type": "union",
    "target": {"type": "box", "x": 80, "y": 40, "z": 20,
               "position": {"x": 0, "y": 0, "z": 0}},
    "tool":   {"type": "box", "x": 5, "y": 5, "z": 20,
               "position": {"x": 0, "y": -22.5, "z": 0}}
  }
}
```
Rule: rib position.y = -(solid_y/2 + rib_y/2) = -(20 + 2.5) = -22.5 (flush with front face).

## Box with Plate on Top, Flush with Right Edge

**Spec**: "30mm cube, plate 10x30x50mm on top face, positioned at the right edge (flush with +X face)"

POSITION RULES for "plate on TOP face, flush with one side edge":
- position.z = solid_z/2 + plate_z/2  (plate sits on top of base)
- position.x = solid_x/2 - plate_x/2  (plate flush with +X face: right edge of plate = right edge of cube)
- position.y = 0  (centered along Y)

Example:
- Cube 30x30x30, Plate 10x30x50
- position.x = 30/2 - 10/2 = 15 - 5 = 10
- position.y = 0
- position.z = 30/2 + 50/2 = 15 + 25 = 40

```json
{
  "description": "30x30x30mm cube with 10x30x50mm plate on top, flush with right (+X) face",
  "root": {
    "type": "union",
    "target": {"type": "box", "x": 30, "y": 30, "z": 30,
               "position": {"x": 0, "y": 0, "z": 0}},
    "tool":   {"type": "box", "x": 10, "y": 30, "z": 50,
               "position": {"x": 10, "y": 0, "z": 40}}
  }
}
```

Flush-with-edge position formula:
- Flush with +X: tool.position.x = solid_x/2 - tool_x/2
- Flush with -X: tool.position.x = -(solid_x/2 - tool_x/2)
- Flush with +Y: tool.position.y = solid_y/2 - tool_y/2
- Flush with -Y: tool.position.y = -(solid_y/2 - tool_y/2)
