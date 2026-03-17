# Common CadQuery Errors and Fixes

## RULE: NEVER add fillet/chamfer unless the blueprint explicitly specifies it
# If the blueprint has no fillet/chamfer node → do NOT call .fillet() or .chamfer()
# Adding unsolicited fillets changes the geometry and makes the validator fail.
# WRONG: result = result.edges().fillet(2.0)  ← unless blueprint has fillet node
# RIGHT: only add fillet/chamfer when blueprint["root"]["type"] == "fillet"/"chamfer"

## Error: "No pending wires" or "No pending faces"
Cause: Trying to extrude/cut without first creating a 2D sketch.
Fix: Always create a shape (rect, circle, polygon) before extrude/cutBlind.

WRONG:
result = cq.Workplane("XY").box(20,20,10).faces(">Z").workplane().extrude(5)

RIGHT:
result = cq.Workplane("XY").box(20,20,10).faces(">Z").workplane().rect(10,10).extrude(5)

---

## Error: "BRep_API: command not done" or OCCT kernel error
Cause: Usually a boolean operation that creates invalid geometry.
Common triggers:
  - Fillet radius too large for the edge
  - Cutting a hole larger than the solid
  - Shell thickness too large

Fix:
  - Reduce fillet/chamfer radius
  - Ensure hole diameter < solid dimension
  - Reduce shell thickness
  - Try .edges("|Z") instead of .edges() for fillets

---

## Error: "Shape is null"
Cause: An operation returned nothing — usually a bad selector.
Fix: Check that the face/edge selector matches your geometry.
  - ">Z" selects the single highest face
  - "<Z" selects the single lowest face
  - If multiple faces at same height, use .faces(">Z").first()

---

## Error: "export needs a shape argument" or AttributeError on export
Cause: `result` is a Workplane object, not a Shape. OR export syntax wrong.
Fix:
WRONG:  result.exportStl("output.stl")
RIGHT:  cq.exporters.export(result, OUTPUT_PATH)

---

## Error: holes appear on wrong face
Cause: Workplane not set to correct face before drilling.
Fix: Always use .faces(">Z").workplane() before placing holes.

WRONG:
result = cq.Workplane("XY").box(40,40,10).hole(5)  # drills through side!

RIGHT:
result = cq.Workplane("XY").box(40,40,10).faces(">Z").workplane().hole(5)

---

## Error: Operation order matters — features before base fail
Cause: Trying to cut a hole before the solid exists.
Fix: Always follow this order:
  1. Create base solid (box, cylinder, etc.)
  2. Add material (extrude, union)
  3. Remove material (holes, cuts, shell)
  4. Add finishing (fillet, chamfer) — ALWAYS LAST

---

## Error: Multiple solids / "CompSolid" issues
Cause: Union not called when combining shapes.
Fix: Explicitly union shapes that should be one solid.
result = shape1.union(shape2)

---

## Error: cutBlind depth wrong direction
Cause: cutBlind needs negative value to cut INTO the solid from the top face.
Fix:
WRONG: .cutBlind(10)   # tries to cut outward, fails or wrong direction
RIGHT: .cutBlind(-10)  # cuts 10mm inward/downward

---

## Error: ImportError for cadquery
Cause: Running without the virtual environment.
Fix: Always use `uv run` to execute scripts.
Note: import cadquery as cq is already injected — do NOT add it yourself.

---

## Performance tip: complex fillets
If .edges().fillet(r) fails on a complex shape, try:
  1. .edges("|Z").fillet(r)  — only vertical edges
  2. Reduce radius
  3. Apply fillet before holes/cuts (on simpler geometry)
  4. Split into multiple fillet calls with smaller selections
