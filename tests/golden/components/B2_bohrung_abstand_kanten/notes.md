# B2 — Bohrung Abstand von Kanten

**Spec-Variation 1:** "200mm wuerfel, oben eine 10mm bohrung von der oberen kante 20mm und von rechter kante 30mm entfernt 5 tief"
**Spec-Variation 2:** "200mm wuerfel, oben 10mm bohrung mit abstand 20 von oben und 30 von rechts 5 tief"
**Spec-Variation 3:** "200mm wuerfel, oben oben 20mm rechts 30mm entfernt eine 10mm bohrung 5 tief"

## Resolver-Mathe

Bohrung auf >Z Face (face_w=200, face_h=200), parent_w/2 = 100,
parent_h/2 = 100.

`edge_distances = {top: 20, right: 30}` mit Edge-from-Edge-Mathe:
- right=30 → offset_x = +(parent_w/2 - 30) = +(100-30) = +70
- top=20   → offset_y = +(parent_h/2 - 20) = +(100-20) = +80

→ `placement.offset_x = 70, offset_y = 80, face = ">Z"`

## Coverage

Phase 1 — Resolver. Phase 2 erweitert um Pipeline-Goldens.
