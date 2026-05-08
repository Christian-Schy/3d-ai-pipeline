# B1 — Bohrung Versatz aus Mitte

**Spec-Variation 1:** "200mm wuerfel, oben eine 10mm bohrung 10mm nach rechts und 20mm nach oben versetzt 5 tief"
**Spec-Variation 2:** "200mm wuerfel, oben eine 10mm bohrung um 10 nach rechts versetzt um 20 nach oben versetzt 5 tief"
**Spec-Variation 3:** "200mm wuerfel, oben 10mm nach rechts 20mm nach oben versetzt eine 10mm bohrung 5mm tief"

Alle drei Varianten muessen das gleiche Blueprint produzieren.

## Resolver-Mathe

Bohrung auf >Z Face (face_w=200 entlang X, face_h=200 entlang Y).

`center_offset = {top: 20, right: 10}` mit `_EDGE_AXIS_MAP[">Z"]`:
- right → wx+1 → offset_x = +10
- top   → wy+1 → offset_y = +20

→ `placement.offset_x = 10, offset_y = 20, face = ">Z"`

## Coverage

Phase 1 — nur Resolver (deterministisch). Phase 2 erweitert um
Pipeline-Goldens fuer die drei Spec-Variationen.
