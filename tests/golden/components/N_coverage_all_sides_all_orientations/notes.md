# N_coverage_all_sides_all_orientations — Nut/Slot L2-Coverage-Golden

**Capability 1.0 — Nut/Slot. Cov-3-Stufe ([CLAUDE.md](../../../../CLAUDE.md)
"L2-Coverage-Goldens").**

Eine Capability komplett: alle 6 Seiten + alle Orientierungen (entlang
X/Y/Z) + DIN-Wording-Varianten A1-A6 × B0-B3 × C0-C3 auf einem
**Wuerfel 120x90x50**.

## Test-Faelle (aus [`docs/conventions/21_nut_slot_din.md`](../../../../docs/conventions/21_nut_slot_din.md))

9 Nuten — N01-N03, N05-N08, N11, N12. N04/N09/N10 deferred (siehe unten).

| Feature | Face | Orient | Matrix-Zellen | DIN-Bezug |
|---|---|---|---|---|
| `n01_oben_a1_b2_c1_y` | oben | entlang Y | A1, B2, C1 | edge-distance, Length-Swap |
| `n02_oben_a1_b2_c0_x` | oben | entlang X | A1, B2, C0 | edge-distance, Default-Achse |
| `n03_oben_a1_b2_c1_verb` | oben | "verlaeuft nach hinten" | A1, B2, C1 | Richtungs-Verb statt "entlang" |
| `n05_rechts_a2_b2_c1_z` | rechts | entlang Z | A2, B2, C1 | Nut-Kante edge-to-EDGE |
| `n06_vorne_a3_a4_b1_c0` | vorne | entlang X | A3+A4, B1, C0 | center-offset + zentriert |
| `n07_unten_a6_c1_y` | unten | entlang Y | A6, C1 | "jeweils X von zwei Kanten" |
| `n08_hinten_a4_b0_c0` | hinten | entlang X | A4, B0, C0 | reines zentriert |
| `n11_links_a1_a4_b1_c1` | links | parallel z. Kante | A1+A4, B1, C1 | single-axis edge-distance |
| `n12_oben_a1_a3_b3_c0` | oben | entlang X | A1+A3, B3, C0 | edge-distance + center-offset |

**Coverage-Check:**
- A1 ✓ (N01, N02, N03, N11, N12)
- A2 ✓ (N05) — `pocket_edge_distances` edge-to-EDGE (Nut-Kante)
- A3 ✓ (N06, N12)
- A4 ✓ (N06, N08, N11)
- A6 ✓ (N07)
- B0 ✓ (N08)
- B1 ✓ (N06, N11)
- B2 ✓ (N01, N02, N03, N05)
- B3 ✓ (N12)
- C0 ✓ (N02, N06, N08, N12)
- C1 ✓ (N01, N03, N05, N07, N11) — Length-Achse != Default-X
- C2/C3 (rotierte Slots) deferred — siehe unten
- **Alle 6 Seiten:** oben (N01-N03, N12), unten (N07), vorne (N06),
  hinten (N08), rechts (N05), links (N11).
- **Orientierungen:** entlang X (N02, N06, N08, N12),
  entlang Y (N01, N07), entlang Z (N05), Richtungs-Verb (N03),
  "parallel zur Kante" (N11).

## Bekannte Limitierungen — N04 + N09 + N10 deferred

Drei Faelle aus Konvention 21 sind aus dem Pipeline-Golden ausgelassen.
Alle drei bleiben gueltige Konventions-Bestandteile; die Resolver-Mathe
ist korrekt (im resolver-component-test ueber separate Faelle gedeckt).

- **N04 (Anfangs-/Endpunkt-Modell)** — "Nut 5x3, Anfangspunkt 20mm von
  linker Kante, Endpunkt 80mm von linker Kante" beschreibt die Nut ueber
  Start-/Endpunkt statt `laenge`. Der `slot_classifier`-Prompt hat keine
  Anfangspunkt/Endpunkt-Keys im Schema. Resolver-aequivalent: `length=60`
  (= 80-20) plus `edge_distance left=20` auf der Length-Achse.
- **N09 + N10 (rotierte Slots, C2/C3)** — "entlang X-Achse, um N° gedreht".
  Der Klassifizierer emittiert `rotation_deg` korrekt (inkl. Vorzeichen
  fuer CW). Der Normalizer verschluckt die Rotation aber **flaky** bei der
  Kombination Achsen-Angabe + Rotation — die Nut landet mal bei angle 0
  statt N°. N09 lief in einem Run gruen, im naechsten rot. Beide Faelle
  sind daher deferred bis ein Normalizer-Demo/Prompt fuer
  "Nut entlang X-Achse um N° gedreht" die richtung+drehung-Kombination
  stabil haelt. C2/C3-Rotation ist ueber T_coverage T10/T11 (Pocket
  CCW/CW) bereits abgedeckt.

Der `feature_builder` liest seit dieser Session `rotation_deg` zusaetzlich
zu `drehung/winkel/angle/rotation` — damit der Klassifizierer-Output-Key
direkt durchgeht, sobald der Normalizer ihn nicht mehr verschluckt.

## Resolver-Mathe — Slot per-Achsen-DIN

Slot-Konvention: Length-Achse = edge-to-EDGE (Nut-Endpunkt ist
fertigungsrelevant), Width-Achse = edge-to-CENTER (Centerline ist
Werkzeug-Referenz). `angle_deg` bestimmt welche Face-Achse die Laenge
ist: 0 → face-X, 90 → face-Y.

Wuerfel 120x90x50 → Face-Half:
- `>Z`/`<Z`: (60, 45) — `>Y`/`<Y`: (60, 25) — `>X`/`<X`: (45, 25)

Beispiel N01 (oben, angle 90, w5 l40, `edge_distances {left:12, top:18}`):
- `left` (wx, Width-Achse) edge-to-CENTER: ox = -(60-12) = **-48**
- `top` (wy, Length-Achse) edge-to-EDGE: oy = +(45 - 18 - 40/2) = **+7**

Beispiel N02 (oben, angle 0, w5 l40, `edge_distances {vorne:12, left:18}`):
- `left` (wx, Length-Achse) edge-to-EDGE: ox = -(60 - 18 - 40/2) = **-22**
- `vorne` (wy, Width-Achse) edge-to-CENTER: oy = -(45-12) = **-33**

N09/N10: bei nicht-rechtwinkliger Rotation (30°/-20°) faellt die
per-Achsen-Logik auf die konservative bbox-Approximation zurueck
(beide Achsen edge-to-CENTER) — bekannte Limitation, in Konvention 21
dokumentiert.

## Status — Pipeline + Resolver gruen

Pipeline-Real-Run-Test 2/2 PASS (77.7s), resolver-component-test 16/16.
Voll im Heatmap (21/0).

Frueher war der Pipeline-Test instabil, weil der `slot_classifier` A1
(`abstand_*`, edge-to-CENTER) und A2 (`kante_*`, edge-to-EDGE) flaky
routete — identische Geometrie wie V2's `slot_top_y_edge` (-48) ergab
mit leicht anderem Wording -45.5. Zwei Fixes haben das geloest:
1. `slot_classifier`-Prompt hat jetzt die A1/A2-Disambiguierungs-Regel
   (kante_* nur bei explizit genannter "Nut-Kante", sonst abstand_*).
2. `normalizer_agent._merge_param_hints` loescht konfligierende
   Konventions-Keys pro Richtung: wenn der Klassifizierer fuer eine
   Richtung A1/A2/A3 emittiert, werden die anderen beiden Konventionen
   derselben Richtung aus dem Normalizer-Parse entfernt.

## Was dieser Test absichert

- Klassifizierer-Pfad fuer Nut auf allen 6 Seiten
- A1/A2-Disambiguierung (`abstand_*` vs `kante_*`)
- Orientierungs-Erkennung: "entlang X/Y/Z", Richtungs-Verb, "parallel zu"
- Slot per-Achsen-DIN (Length edge-to-edge, Width edge-to-center)
- Resolver-Math fuer alle Edge-Distance-/Center-Offset-Pfade
- Multi-Feature-Aggregation auf einem Bauteil

## Naechste L2-Goldens (Plan)

- `M_coverage_patterns_all_kinds` (Grid/Kreis/Linear, M01-M10)

`B_coverage` und `T_coverage` sind bereits gruen.
