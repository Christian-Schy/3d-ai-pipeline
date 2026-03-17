# Planner Examples — feature_subtractive (holes, slots, grooves, pockets)

Rule: cylinder height MUST exceed the solid it cuts through (add 2–4mm extra).
Rule: cylinder radius = hole_diameter / 2.
Rule: For through-holes: depth=null in features; in raw CSG: height = solid_height + 4.
Rule: For blind holes/slots: depth = explicit mm value; tool does NOT exceed solid.

## Box with Central Through-Hole
```json
{
  "description": "40mm cube with 8mm diameter central through-hole",
  "root": {
    "type": "cut",
    "target": {"type": "box", "x": 40, "y": 40, "z": 40,
               "position": {"x": 0, "y": 0, "z": 0}},
    "tool":   {"type": "cylinder", "radius": 4.0, "height": 44,
               "position": {"x": 0, "y": 0, "z": 0}}
  }
}
```

## Box with Offset Through-Hole (not centered)
```json
{
  "description": "60x40x10mm plate with 6mm hole 15mm from left edge, centered Y",
  "root": {
    "type": "cut",
    "target": {"type": "box", "x": 60, "y": 40, "z": 10,
               "position": {"x": 0, "y": 0, "z": 0}},
    "tool":   {"type": "cylinder", "radius": 3.0, "height": 14,
               "position": {"x": -15, "y": 0, "z": 0}}
  }
}
```
Rule: offset from LEFT edge = -(solid_x/2 - distance_from_edge) = -(30 - 15) = -15.

## Box with Blind Slot (surface groove, not through)
```json
{
  "description": "80x40x15mm block with 60x8mm slot, 5mm deep on top face",
  "root": {
    "type": "cut",
    "target": {"type": "box", "x": 80, "y": 40, "z": 15,
               "position": {"x": 0, "y": 0, "z": 0}},
    "tool":   {"type": "box", "x": 60, "y": 8, "z": 5,
               "position": {"x": 0, "y": 0, "z": 5}}
  }
}
```
Rule: slot tool position.z = solid_height/2 - slot_depth/2 = 7.5 - 2.5 = 5.0.
Rule: slot stays ON SURFACE — use blind depth, never cutThruAll for surface slots.
