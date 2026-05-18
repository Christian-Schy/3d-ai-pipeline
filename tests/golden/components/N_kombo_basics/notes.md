# N_kombo_basics — 9 Nut-Variationen auf 100mm Wuerfel

Stress-Test fuer Nuten-Resolver-Mathe. Deckt N1+N2 (Mittelpunkt-Methoden,
Phase N.1 ohne Schema-Erweiterung) sowie zusaetzliche Patterns (Anchor,
Rotation, andere Face) ab.

User-Spec (Phase N.1 — Combo aus 9 Variationen):

> 100mm wuerfel, oben eine nut 5x5 entlang x-achse laenge 30mm zentral,
> oben eine nut 5x5 entlang y-achse laenge 40mm 10mm nach rechts versetzt,
> oben eine nut 5x5 entlang x-achse 10mm nach rechts versetzt,
> oben eine nut 5x5 entlang y-achse laenge 40mm von oberer kante 30mm und
> von linker kante 20mm entfernt,
> oben eine nut 5x5 entlang x-achse laenge 50mm von rechter kante 30mm und
> 10mm aus mitte nach unten,
> rechts eine nut 5x5 entlang y-achse laenge 40mm mittig,
> oben eine nut 5x5 entlang y-achse laenge 40mm liegt auf rechter kante an,
> 10mm nach oben versetzt,
> oben eine nut 5x5 entlang y-achse laenge 30mm obere rechte ecke 10mm nach
> unten und 20mm nach links versetzt,
> oben eine nut 5x5 entlang x-achse laenge 50mm 15 grad gegen uhrzeigersinn
> gedreht zentral.

## Konventionen

- params: {length, width, depth} — length = entlang Slot-Achse,
  width = senkrecht dazu, depth = in die Face hinein.
- `edge_distances` bei Slots ist edge-to-center wie bei Bohrungen.
- `pocket_edge_distances` bei Slots ist explizit edge-to-edge:
  Nut-Kante zu Parent-Kante, mit Slot-Footprint aus length/width.
- placement.angle_deg encoded:
  - 0 = Slot entlang horizontaler Face-Achse (face WX)
  - 90 = Slot entlang vertikaler Face-Achse (face WY)
  - andere Werte = echte Rotation um Slot-Mittelpunkt
- Auf >Z Face: WX=X, WY=Y. "entlang x-achse" → angle=0, "entlang y-achse" → angle=90.
- Auf >X Face: WX=Y, WY=Z. "entlang y-achse" → angle=0, "entlang z-achse" → angle=90.
- Echte Rotation kombiniert mit Achsen-Konvention:
  "entlang x-achse + 15 grad gedreht" → angle = 0 + 15 = 15.

## Resolver-Mathe (verifiziert gegen src/tools/blueprint_resolver.py)

100mm Wuerfel → face >Z: parent_w=parent_h=100, half=50,50.
Face >X: parent_w=100 (y), parent_h=100 (z), half=50,50.
Slot mit `edge_distances` ist hole-like → child_half=0.
Slot mit `pocket_edge_distances` ist edge-to-edge → child_half aus Slot-Footprint.

### Variationen

| ID | Pattern | semantic | Mathe | offset_x | offset_y | angle_deg | params |
|----|---------|----------|-------|----------|----------|-----------|--------|
| nut_zentral_x_l30 | Standard mittig | alignment centered, kein offset | 0, 0 | 0 | 0 | 0 | l30 w5 d5 |
| nut_versatz_rechts_y_l40 | Versatz + Achse | center_offset{right:10}, entlang y | +10, 0 | 10 | 0 | 90 | l40 w5 d5 |
| nut_versatz_rechts_x_durchg | Versatz auf Achsen-Achse, durchgaengig | center_offset{right:10}, length=100 | +10, 0 | 10 | 0 | 0 | l100 w5 d5 |
| nut_kanten_top30_left20_y_l40 | edge_distances zwei Achsen (Mittellinie) | edge{top:30, left:20}, entlang y | Mittellinien-Bezug beide Achsen | -30 | 20 | 90 | l40 w5 d5 |
| nut_mix_axes_x_l50 | Mischung B3 (A1 + A3) | edge{right:30} + center{bottom:10}, entlang x | +(50-30), -10 | 20 | -10 | 0 | l50 w5 d5 |
| nut_rechts_face_y_l40 | Andere Face | side=rechts, alignment centered | 0, 0 (auf >X) | 0 | 0 | 0 | l40 w5 d5 |
| nut_anchor_right_edge_y_l40 | Anchor Kante + Offset | anchor{right_edge, offset{top:10}}, entlang y | (+50, 0) + (0, +10) | 50 | 10 | 90 | l40 w5 d5 |
| nut_ecke_oben_rechts_y_l30 | Ecken-Regel (zwei abstand_*) | edge{top:25, right:20}, entlang y | Mittellinien-Bezug beide Achsen | 30 | 25 | 90 | l30 w5 d5 |
| nut_rotated_x_l50 | Mit Rotation | alignment centered, angle 15° CCW, entlang x | 0, 0, angle 0+15=15 | 0 | 0 | 15 | l50 w5 d5 |

### Detail-Mathe pro Variation

**nut_kanten_top30_left20_y_l40:**
- Mittellinien-Bezug (Konv. 21, beide Achsen edge-to-CENTER, kein
  child_half-Abzug — Slot ist hole-like).
- top:30 → wy, oy = +(50 - 30) = +20 → Mittellinie 30mm vom oberen Rand
- left:20 → wx, ox = -(50 - 20) = -30 → Mittellinie 20mm vom linken Rand
- Geometrie-Check: Slot y ∈ [0, 40], x ∈ [-32.5, -27.5] — innerhalb.

**nut_mix_axes_x_l50** (Mischung Achsen A1+A3 unter Mittellinien-Regel):
- Spec "von rechter kante 30mm" → A1 `abstand_rechts:30` (per Konv. 10
  "von der Kante" → A1, "die Kante" → A2). Mittellinien-Bezug:
  ox = +(50 - 30) = +20.
- Spec "10mm aus mitte nach unten" → A3 `versatz_unten:10` →
  oy = -10 (center-relativ).
- Resolver: edge_distances setzt wx-Achse → ox=+20; center_offset
  promoviert auf wy-Achse → oy=-10.

**nut_anchor_right_edge_y_l40:**
- parent_point=right_edge auf >Z: (+0.5, 0) * (100, 100) = (+50, 0)
- child_point=center: (0, 0)
- ox = 50 - 0 = +50, oy = 0 - 0 = 0
- offset {top:10} → wy +1, val=10 → +10
- ox = +50, oy = 0 + 10 = +10

**nut_ecke_oben_rechts_y_l30** (Ecken-Regel, "obere rechte Ecke …
versetzt"):
- Ecken-Phrase → Ecken-Regel → zwei `abstand_*` → `edge_distances` (kein
  separater Anker, siehe `10_masseintragung_din406.md`).
- Mittellinien-Bezug auf beiden Achsen (Konv. 21).
- right:20 → wx, ox = +(50 - 20) = +30 → Mittellinie 20mm vom rechten Rand
- top:25 → wy, oy = +(50 - 25) = +25 → Mittellinie 25mm vom oberen Rand
- Geometrie-Check: Nut y ∈ [10, 40], x ∈ [27.5, 32.5] — innerhalb.
- Hinweis: Die zu Schritt-1-Zeiten populaere Spec-Phrase "10mm nach unten
  versetzt" wuerde unter Mittellinien-Bezug die Mittellinie 10mm von der
  Kante platzieren → Nut-Ende bei +55 → ragt 5mm raus. Daher hier
  top:25 (Mittellinie 25mm) als sauberer Eck-Slot.

## Coverage

- center_offset (Versatz): nut_versatz_rechts_y_l40, nut_versatz_rechts_x_durchg
- edge_distances zwei Achsen: nut_kanten_top30_left20_y_l40
- Mischung Achsen B3: nut_mix_axes_x_l50 (`pocket_edge_distances` + `center_offset`)
- anchor parent_point=edge: nut_anchor_right_edge_y_l40
- Ecken-Regel (zwei abstand_*, DIN per-Achse): nut_ecke_oben_rechts_y_l30
- echte Rotation: nut_rotated_x_l50
- Andere Face (>X): nut_rechts_face_y_l40
- explizite Laenge vs durchgaengig: alle haben explizite Laenge ausser nut_versatz_rechts_x_durchg

NICHT abgedeckt (siehe ADR 0005 Phase N.2 fuer Schema-Erweiterung):
- Start-Endpunkt-Modell (Modell 1): "startet ... geht ... nach ..."
- Endform Verrundung
- Andere Faces (<X, >Y, <Y, <Z) — Sign-Spiegelung schon durch Bohrungs-Goldens validiert
