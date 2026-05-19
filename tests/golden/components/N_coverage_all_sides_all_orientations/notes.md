# N_coverage_all_sides_all_orientations — Nut/Slot L2-Coverage-Golden

**Capability 1.0 — Nut/Slot. Cov-3-Stufe ([CLAUDE.md](../../../../CLAUDE.md)
"L2-Coverage-Goldens").**

Eine Capability komplett: alle 6 Seiten + alle Orientierungen (entlang
X/Y/Z) + DIN-Wording-Varianten A1-A6 × B0-B3 × C0-C3 auf einem
**Wuerfel 120x90x50**.

## Test-Faelle (aus [`docs/conventions/21_nut_slot_din.md`](../../../../docs/conventions/21_nut_slot_din.md))

12 Nuten — N01-N12, vollstaendig. Keine deferred Cases mehr.
N09 + N10 ab Phase A aktiv (rotierte Slots, Slot-Klassifizierer
A1/A2-Regel + Normalizer-Konflikt-Aufloesung 87af981). N04 ab Phase B
aktiv (Anfangs-/Endpunkt-Modell, ADR-0010-Muster: `anfang_*`/`ende_*`
Klassifizierer-Hints, `feature_builder` rechnet `laenge`).

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
- C2 ✓ (N09) — rotierter Slot CCW +30°
- C3 ✓ (N10) — rotierter Slot CW -20°
- **Alle 6 Seiten:** oben (N01-N03, N12), unten (N07), vorne (N06),
  hinten (N08), rechts (N05), links (N11).
- **Orientierungen:** entlang X (N02, N06, N08, N12),
  entlang Y (N01, N07), entlang Z (N05), Richtungs-Verb (N03),
  "parallel zur Kante" (N11).

## Phase A — N09 + N10 reaktiviert (2026-05-16)

Vorher deferred. Re-aktivierungs-Grundlage: der Slot-Klassifizierer-
A1/A2-Regel-Fix (Commit 87af981) plus die agent-agnostische Normalizer-
Konflikt-Aufloesung (`_merge_param_hints` loescht konkurrierende
Konventions-Keys derselben Richtung) erzwingen jetzt eine konsistente
Konventions-Wahl pro Achse. Die bereits vorhandenen Normalizer-Demos
`norm_slot_axb_entlang_laenge_rotation_ccw` (N09 CCW-Vorbild) und
`norm_slot_axb_entlang_laenge_rotation_cw` (N10 CW-Vorbild) decken
"Nut entlang X-Achse um N° gedreht" stabil ab.

N09/N10 sind aktiv und nach der Mittellinien-Migration weiterhin
deterministisch: `abstand_*` setzt den Slot-Mittelpunkt, Rotation ist
kein Sonderfall.

## Phase B — N04 aktiviert (2026-05-16)

Vorher deferred ("`slot_classifier` hat keine Anfangspunkt/Endpunkt-Keys").
Schema-getrieben geloest (ADR-0010-Muster):

- **Klassifizierer-Schema** additiv um `anfang_<kante>` / `ende_<kante>`
  erweitert (12 Zahlen-Keys). Der `slot_classifier`-Prompt lehrt:
  zwei Endpunkt-Distanzen + Bezugskante extrahieren, NICHT die Laenge
  rechnen, `richtung` aus den Punkten ableiten.
- **`feature_builder._resolve_slot_endpoints`** bildet deterministisch
  `laenge = |ende - anfang|` und `abstand_<kante> = (anfang+ende)/2`
  (Mittelpunkt der Endpunkte = Slot-Mittellinie). Reine Arithmetik —
  kein Sprachverstaendnis im Code.
- 2 Klassifizierer-Demos (X-/Y-Achse) + 1 Normalizer-Demo +
  Normalizer-Prompt-Beispiel. N04 als `n04_oben_a1_b2_c0_endpoints` in
  Pipeline + Resolver Golden.

Keine deferred Cases mehr in N_coverage — 12/12.

Der `feature_builder` liest seit dieser Session `rotation_deg` zusaetzlich
zu `drehung/winkel/angle/rotation` — damit der Klassifizierer-Output-Key
direkt durchgeht, sobald der Normalizer ihn nicht mehr verschluckt.

## Resolver-Mathe — Slot-Mittellinien-Bezug

Slot-Konvention seit 2026-05-18: `abstand_*` misst auf beiden Achsen
von der Bauteilkante zur Slot-Mittellinie / zum Slot-Mittelpunkt.
`pocket_edge_distances` bleibt der explizite edge-to-EDGE-Pfad fuer
Restwandstaerke-/Endkanten-Bemassung.

Wuerfel 120x90x50 → Face-Half:
- `>Z`/`<Z`: (60, 45) — `>Y`/`<Y`: (60, 25) — `>X`/`<X`: (45, 25)

Beispiel N01 (oben, angle 90, w5 l40, `edge_distances {left:12, top:18}`):
- `left` (wx) Mittellinie: ox = -(60-12) = **-48**
- `top` (wy) Mittellinie: oy = +(45-18) = **+27**

Beispiel N02 (oben, angle 0, w5 l40, `edge_distances {vorne:12, left:18}`):
- `left` (wx) Mittellinie: ox = -(60-18) = **-42**
- `vorne` (wy) Mittellinie: oy = -(45-12) = **-33**

N09/N10: bei nicht-rechtwinkliger Rotation (30°/-20°) bleibt die
Position Mittelpunkt + Winkel. Die Aussenkontur wird separat durch den
Restwandstaerke-Validator AABB-bewusst geprueft.

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
- Slot-Mittellinien-Bezug (`abstand_*` edge-to-center auf beiden Achsen)
- Resolver-Math fuer alle Edge-Distance-/Center-Offset-Pfade
- Multi-Feature-Aggregation auf einem Bauteil

## Naechste L2-Goldens (Plan)

- `M_coverage_patterns_all_kinds` (Grid/Kreis/Linear, M01-M10)

`B_coverage` und `T_coverage` sind bereits gruen.
