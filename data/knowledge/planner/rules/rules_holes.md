## Hole Rules

- diameter is in mm directly — NOT radius (blueprint stores diameter)
- depth=null → through-hole (cutThruAll). depth=10 → cutBlind 10mm.
- Use hole_pattern (positions list) for 2+ holes — NOT separate hole nodes.
- Hole ordering: ALL holes BEFORE any slot on the same face.
- cbore_hole: flat-bottom recess + through-hole (socket-head screws)
- csk_hole: tapered recess (flat-head screws), default angle=82°
- pushPoints positions are ABSOLUTE from face bbox center (not relative to each other).

## Depth Handling — CRITICAL

- Spec says "Xmm tief/deep" → depth=X (BLIND hole), NEVER depth=null!
- Spec says "durchgehend/through/komplett durch" → depth=null (through-hole)
- No depth mentioned → depth=null (through by default)
- NEVER silently change a specified depth to null

Examples:
  "Bohrung 10mm Ø, 29mm tief"  → depth=29   ← BLIND
  "Bohrung 10mm durchgehend"   → depth=null  ← THROUGH
  "Bohrung 10mm"               → depth=null  ← THROUGH (default)
