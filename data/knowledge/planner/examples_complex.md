# Planner Examples — complex_multi_step (combined operations)

Rule: Build CSG tree bottom-up: primitives first, then cuts, then unions, fillet last.
Rule: Boolean order matters — cut holes BEFORE applying fillet.
Rule: For stacked parts at different Z heights, position.z = part1_height/2 + part2_height/2.

## Mounting Plate with Corner Holes and Fillet
```json
{
  "description": "100x80x6mm mounting plate, 4x M5 corner holes (10mm from edges), 3mm fillet",
  "root": {
    "type": "fillet",
    "radius": 3.0,
    "edges": "|Z",
    "child": {
      "type": "cut",
      "target": {"type": "box", "x": 100, "y": 80, "z": 6,
                 "position": {"x": 0, "y": 0, "z": 0}},
      "tool": {
        "type": "union",
        "target": {"type": "cylinder", "radius": 2.5, "height": 9, "position": {"x":  40, "y":  30, "z": 0}},
        "tool": {
          "type": "union",
          "target": {"type": "cylinder", "radius": 2.5, "height": 9, "position": {"x": -40, "y":  30, "z": 0}},
          "tool": {
            "type": "union",
            "target": {"type": "cylinder", "radius": 2.5, "height": 9, "position": {"x":  40, "y": -30, "z": 0}},
            "tool":   {"type": "cylinder", "radius": 2.5, "height": 9, "position": {"x": -40, "y": -30, "z": 0}}
          }
        }
      }
    }
  }
}
```
Positions: x=±(100/2-10)=±40, y=±(80/2-10)=±30. Fillet wraps the entire cut result.

## Box with Boss and Through-Hole (additive + subtractive)
```json
{
  "description": "60x60x12mm base plate with 20mm diameter, 10mm boss on top and 8mm through-hole in boss",
  "root": {
    "type": "cut",
    "target": {
      "type": "union",
      "target": {"type": "box", "x": 60, "y": 60, "z": 12,
                 "position": {"x": 0, "y": 0, "z": 0}},
      "tool":   {"type": "cylinder", "radius": 10.0, "height": 10,
                 "position": {"x": 0, "y": 0, "z": 11}}
    },
    "tool": {"type": "cylinder", "radius": 4.0, "height": 26,
             "position": {"x": 0, "y": 0, "z": 0}}
  }
}
```
Rule: union (base+boss) first, then cut the hole through both. Order matters.
Rule: boss position.z = base_height/2 + boss_height/2 = 6 + 5 = 11.
Rule: through-hole height = base_height + boss_height + 4 = 26.
