## Fillet / Chamfer Rules

- Fillets/chamfers ALWAYS wrap their parent node — never inside a cut tool.
- Apply AFTER all boolean operations and features.
- fillet radius must be ≤ half the smallest adjacent edge length.
- chamfer distance must be ≤ half the smallest adjacent edge length.

Edge selectors (valid CadQuery strings — do NOT use "all", it is invalid):
  ""        → ALL edges (no filter — use this when the spec says "all edges")
  "|Z"      → vertical edges only (parallel to Z — the 4 side corner edges of a box)
  "#Z"      → horizontal edges only (top + bottom perimeter of a box)
  ">Z"      → top-most edges only
  "<Z"      → bottom-most edges only
  "%CIRCLE" → circular edges only

For "all edges": set edges="" (empty string). Coder generates .edges().fillet(r) or .edges().chamfer(d).
For "vertical edges only": set edges="|Z"
For "top edges only": set edges=">Z"

⚠ Do NOT set edges="|Z" when the spec says "all edges" — that only selects 4 vertical corner edges!

Structure: modifier wraps the complete geometry:
  {"type": "chamfer", "distance": 2.0, "edges": "",
   "child": {"type": "box", "x": 30, "y": 30, "z": 30, ...}}   ← all edges

  {"type": "fillet", "radius": 2.0, "edges": "|Z",
   "child": {"type": "box", "x": 30, "y": 30, "z": 10, ...}}   ← vertical only

Shell (hollow box with open top):
  {"type": "shell", "thickness": 2.0, "open_face": ">Z",
   "child": <box or union>}
