# 21 — Nut / Slot Bemassung (DIN-konform per Achse)

## Konvention

Slots/Nuten haben **zwei verschieden zu behandelnde Achsen**:

- **Length-Achse** (Slot-Verlauf, z.B. 40mm lange Nut entlang Y) →
  **edge-to-EDGE** (Slot-Endpunkt zur Bauteilkante).
- **Width-Achse** (Slot-Querrichtung, z.B. 5mm Breite) →
  **edge-to-CENTER** (Centerline zur Bauteilkante).

Begruendung (DIN-Praxis):
- Die **Centerline** des Slots ist die fertigungsrelevante Referenz fuer
  die Width-Achse — das Werkzeug folgt der Mittellinie. Der Konstrukteur
  bemasst zur Mittellinie.
- Die **Endpunkte** des Slots (Anfang und Ende der Endrundungen) sind
  fertigungsrelevant fuer die Length-Achse — Werkzeug-Anfahrt,
  Restwandstaerke, Toleranz zur naechsten Geometrie. Der Konstrukteur
  bemasst zur Slot-Aussenkante in Length-Richtung.

## Wording-Beispiele

Wuerfel 120x90x50, Nut 5x3 (Width × Tiefe), Laenge 40mm entlang Y-Achse
(angle_deg=90 → wy ist Length-Achse, wx ist Width-Achse):

| Phrase | Klassifizierer-Output | Resolver-Output | Geometrie |
|---|---|---|---|
| "von linker Kante 12mm" | `abstand_links: 12` | `ox = -W/2 + 12 = -48` (edge-to-CENTER) | Centerline 12mm vom linken Rand |
| "von oberer Kante 18mm" | `abstand_oben: 18` | `oy = +H/2 - 18 - L/2 = +7` (edge-to-EDGE per DIN-Slot-Konvention) | Slot-Top-Edge 18mm vom oberen Rand |

Das LLM emittiert in BEIDEN Faellen `abstand_*` (Default-Konvention aus
[`10_masseintragung_din406.md`](10_masseintragung_din406.md)). Der
**Resolver** unterscheidet je Achse weil er weiss welche Achse Length
und welche Width ist (aus `angle_deg` und Slot-Achse).

Bei expliziter Phrase "deren obere Kante 18mm von oberer Wuerfelkante" →
`kante_oben: 18` → wird im Resolver als `pocket_edge_distances` behandelt
(forciert edge-to-EDGE auf beiden Achsen, ueberschreibt Default).

## Edge-Cases

### Slot-Rotation ungleich 0°/90°/180°

Bei z.B. 30° gedrehter Slot ist die Length-Achse keine reine wx oder wy.
Der Resolver faellt in dem Fall auf das Default-Verhalten (edge-to-CENTER
auf beiden Achsen) zurueck. Das ist konservativ — der Slot landet evtl.
naeher am Rand als gewollt, aber nicht ausserhalb.

Konstrukteur sollte bei stark gedrehten Slots `pocket_edge_distances`
explizit verwenden ("deren X-Kante ...") oder einen Anchor-Punkt setzen.

### Slot-Width klein vs Slot-Length gross

Bei sehr schmalen Slots (Width <= 3 mm) ist der Unterschied
edge-to-CENTER vs edge-to-EDGE auf der Width-Achse minimal (≤1.5mm).
Der Konstrukteur akzeptiert beide Lesarten implizit. Keine Sonderbehandlung.

Bei langen Slots (Length >= 30 mm) ist der Unterschied auf der Length-
Achse kritisch — die Slot-Endpunkte koennen sonst ueber die Bauteilkante
hinaus ragen. Genau diese Fall-Klasse triggerte die Konvention.

### Slot mit `pocket_edge_distances` (explizit edge-to-EDGE)

Wenn die Phrase "deren X-Kante" sagt, gewinnt `pocket_edge_distances`
auf BEIDEN Achsen (auch Width). Das ist die explizite Konstrukteur-
Forderung "die Nut-Kante exakt X mm vom Rand". Das LLM uebergibt
beide Felder; der Resolver `pocket_edge_distances`-Pfad ueberschreibt
die Default-Slot-Per-Achse-Logik.

### Bemassung bei rotierter Nut (≠ 90er)

Bei rotierten Nuten (C2/C3, Rotation ungleich Vielfache von 90°) bemasst
der Konstrukteur **immer zum Nut-CENTER**, nicht zu einer Length-Kante.
Begruendung: Length-Kanten sind nach Rotation diagonal — keine sinnvolle
DIN-Bezugskante mehr. Der Resolver faellt deshalb auf edge-to-CENTER fuer
**beide** Achsen zurueck (siehe auch oben "Slot-Rotation ungleich 0°/90°/
180°").

Beispiel N09: "Vorne eine Nut 5x3, 30mm lang entlang X, um 30° gedreht,
von linker Kante 30mm und von unterer Kante 15mm" → beide `abstand_*`-Werte
sind zum Nut-CENTER, nicht zu Length-Endpunkten.

### Anfangs-/Endpunkt-Phrasen sind self-contained

Wenn Anfangs- und Endpunkt einer Nut beide angegeben werden, ergeben sich
**Achse + Laenge + (bei diagonalen Punkten) Rotation implizit**. Die Phrase
braucht **keine** zusaetzliche `entlang X`- / "verlaeuft nach"-Angabe.
Klassifizierer/Normalizer leitet die Slot-Achse aus den Punkt-Koordinaten ab.

Beispiel N04: "Anfangspunkt 20mm von linker Kante, Endpunkt 80mm von
linker Kante" → beide Punkte teilen die Y-Position (impliziert durch
"von vorderer Kante 30mm"), unterscheiden sich nur im X. Daraus folgt:
Nut verlaeuft entlang X, Laenge = 60mm, Rotation = 0°.

**Code-Pfad (ADR 0011):** Der `slot_classifier` emittiert die zwei
Endpunkt-Distanzen als `anfang_<kante>` / `ende_<kante>` plus `richtung`.
Die Laenge wird NICHT vom LLM gerechnet — `feature_builder.
_resolve_slot_endpoints` bildet `laenge = |ende - anfang|` und
`abstand_<kante> = min(anfang, ende)` deterministisch.

### `versatz_*` referenziert immer Nut-CENTER

Anders als `abstand_*` (das per-Achse-DIN unterschiedlich behandelt:
Length-Achse edge-to-edge, Width-Achse edge-to-center), referenziert
`versatz_*` **immer den Nut-CENTER** — auch auf der Length-Achse. Das ist
die Definition von Achse A3 (center-relativ).

Beispiel N12: "Oben eine Nut 5x3, 40mm lang entlang X, von vorderer Kante
20mm **und 15mm aus der Mitte nach links versetzt**":
- `abstand_vorne: 20` → edge-to-CENTER auf Y (Width-Achse) → Nut-
  Centerline 20mm vom vorderen Rand
- `versatz_links: 15` → **Nut-CENTER** bei -15 auf X (Length-Achse),
  **nicht** der Length-Endpunkt

Wer wirklich den Length-Endpunkt referenzieren will, schreibt
`abstand_links: 15` — dann greift die DIN-Slot-Konvention (Length=edge-to-
edge) und der Nut-Endpunkt landet 15mm vom Bauteilrand.

## Code-Pfad

- **Klassifizierer:** [`data/prompts/prompt_classifier_slot.py`](../../data/prompts/prompt_classifier_slot.py).
  Default-Regel "von X-Kante Y mm" → `abstand_*`. Explizit "die X-Kante"
  → `kante_*`.
- **Feature-Builder:** [`src/tools/feature_builder.py`](../../src/tools/feature_builder.py)
  `_SLOT_AXIS_TO_ANGLE` Mapping side+axis → angle_deg. Slot-Length aus
  Spec ueber `_fill_missing_slot_length` falls fehlend.
- **Resolver per-Achse:** [`src/tools/blueprint_resolver.py`](../../src/tools/blueprint_resolver.py)
  `_compute_offsets`. Branch `if ftype_lower in ("slot", "groove")`
  bestimmt aus `angle_deg` welche Achse Length und welche Width ist,
  setzt `is_box_wx`/`is_box_wy` per-Achse (Length=True → edge-to-EDGE,
  Width=False → edge-to-CENTER).
- **Slot-Footprint:** `_get_child_face_size` mit `feat_type="slot"`
  liefert `(width, length)` oder `(length, width)` je nach `angle_deg`,
  damit `child_h`/`child_w` die korrekten Slot-Dimensionen halten.

## Tests

### Bestehende Tests (Stand pre-Coverage-Matrix)

- Unit: [`tests/tools/test_kante_vs_abstand.py`](../../tests/tools/test_kante_vs_abstand.py)
  `test_kante_top_left_on_y_slot_uses_width_and_length` — explizite
  pocket_edge_distances bei Slot.
- Component-Goldens: [`tests/golden/components/N_kombo_basics/`](../../tests/golden/components/N_kombo_basics/)
  `nut_kanten_top30_left20_y_l40` — `abstand_*` mit per-Achse-DIN-Logik
  (ox=-30 edge-to-CENTER, oy=0 edge-to-EDGE).
- Pipeline-Goldens: [`tests/golden/components/V2_balanced_feature_palette/`](../../tests/golden/components/V2_balanced_feature_palette/)
  `slot_top_y_edge` — Real-Pipeline-Verifikation, ox=-48, oy=+7.
- DSPy-Demos: 8 Slot-Demos in [`data/dspy_training/klassifizierer_traces.py`](../../data/dspy_training/klassifizierer_traces.py)
  (5 mit `abstand_*` fuer "von X-kante", 3 mit `kante_*` fuer "deren
  X-kante" / "die X-kante" / "liegt X-kante an").

### Coverage-Matrix-Test-Liste (Cov-3-Ergaenzung, Matrix-abgeleitet)

Relevante Matrix-Zellen (siehe [`11_coverage_matrix.md`](11_coverage_matrix.md)):
**A1, A2, A3, A4, A6** × **B0, B1, B2, B3** × **C0, C1, C2, C3** × **D1, D2**.
A5 (Bauteil-Face-Anker) ist fuer line-like Slots **nicht** relevant.

Bauteil fuer alle Tests: **Wuerfel 120x90x50**.
Pro Test pflegen wir **D1** + **D2**.

| ID | Face | Matrix-Zellen | D1 (Feature → Position) | D2 (Position → Feature) |
|---|---|---|---|---|
| **N01** | oben | A1, B2, **C1** *(entlang Y, length-swap)* | "Wuerfel 120x90x50. Oben eine Nut 5 breit, 3 tief, 40mm lang entlang Y-Achse, von linker Kante 12mm und von oberer Kante 18mm." | "Wuerfel 120x90x50. Oben 12mm von linker Kante und 18mm von oberer Kante eine Nut 5x3, 40mm lang entlang Y-Achse." |
| **N02** | oben | A1, B2, **C0** *(entlang X, default)* | "Wuerfel 120x90x50. Oben eine Nut 5x3, 40mm lang entlang X-Achse, von vorderer Kante 12mm und von linker Kante 18mm." | "Wuerfel 120x90x50. Oben 12mm von vorderer Kante und 18mm von linker Kante eine Nut 5x3, 40mm lang entlang X-Achse." |
| **N03** | oben | A1, B2, C1 — Richtungs-Verb statt "entlang" | "Wuerfel 120x90x50. Oben eine Nut 5x3, 40mm lang, verlaeuft nach hinten, von linker Kante 12mm und von vorderer Kante 18mm." | "Wuerfel 120x90x50. Oben 12mm von linker Kante und 18mm von vorderer Kante eine Nut 5x3, 40mm lang die nach hinten verlaeuft." |
| **N04** | oben | A1, B2, C0 — Anfangs-/Endpunkt statt `laenge` | "Wuerfel 120x90x50. Oben eine Nut 5x3, Anfangspunkt 20mm von linker Kante, Endpunkt 80mm von linker Kante, von vorderer Kante 30mm." | "Wuerfel 120x90x50. Oben, Anfangspunkt 20mm von linker Kante, Endpunkt 80mm von linker Kante, 30mm von vorderer Kante, eine Nut 5x3." |
| **N05** | rechts | **A2**, B2, C1 *(entlang Z)* | "Wuerfel 120x90x50. Rechts eine Nut 4 breit, 2 tief, 30mm lang entlang Z-Achse, die obere Nut-Kante 15mm von der oberen Wuerfelkante." | "Wuerfel 120x90x50. Rechts mit der oberen Nut-Kante 15mm von der oberen Wuerfelkante eine Nut 4x2, 30mm lang entlang Z-Achse." |
| **N06** | vorne | A3+A4, B1, C0 | "Wuerfel 120x90x50. Vorne eine zentrierte Nut 6x4, 50mm lang entlang X-Achse, 5mm aus der Mitte nach oben versetzt." | "Wuerfel 120x90x50. Vorne 5mm aus der Mitte nach oben versetzt eine zentrierte Nut 6x4, 50mm lang entlang X-Achse." |
| **N07** | unten | A6, C1 *(entlang Y)* | "Wuerfel 120x90x50. Unten eine Nut 5x3, 25mm lang entlang Y-Achse, jeweils 10mm von linker und vorderer Kante." | "Wuerfel 120x90x50. Unten jeweils 10mm von linker und vorderer Kante eine Nut 5x3, 25mm lang entlang Y-Achse." |
| **N08** | hinten | A4, B0, C0 | "Wuerfel 120x90x50. Hinten eine zentrierte Nut 6x3, 40mm lang entlang X-Achse." | "Wuerfel 120x90x50. Hinten zentriert eine Nut 6x3, 40mm lang entlang X-Achse." |
| **N09** | vorne | A1, B2, **C2** *(CCW ≠ 90er)* | "Wuerfel 120x90x50. Vorne eine Nut 5x3, 30mm lang entlang X-Achse, um 30° gedreht, von linker Kante 30mm und von unterer Kante 15mm." | "Wuerfel 120x90x50. Vorne 30mm von linker Kante und 15mm von unterer Kante eine Nut 5x3, 30mm lang entlang X-Achse, um 30° gedreht." |
| **N10** | hinten | A1, B2, **C3** *(CW ≠ 90er)* | "Wuerfel 120x90x50. Hinten eine Nut 5x3, 30mm lang entlang X-Achse, um 20° im Uhrzeigersinn gedreht, von rechter Kante 25mm und von unterer Kante 15mm." | "Wuerfel 120x90x50. Hinten 25mm von rechter Kante und 15mm von unterer Kante eine Nut 5x3, 30mm lang entlang X-Achse, um 20° im Uhrzeigersinn gedreht." |
| **N11** | links | A1+A4, B1, **C1** *(parallel zur Kante)* | "Wuerfel 120x90x50. Links eine Nut 4x2, 30mm lang, parallel zur unteren Kante, mittig auf der Hoehe und 15mm von rechter Kante." | "Wuerfel 120x90x50. Links mittig auf der Hoehe und 15mm von rechten Kante eine Nut 4x2, 30mm lang parallel zur unteren Kante." |
| **N12** | oben | A1+A3, **B3**, C0 *(entlang X)* | "Wuerfel 120x90x50. Oben eine Nut 5x3, 40mm lang entlang X-Achse, von vorderer Kante 20mm und 15mm aus der Mitte nach links versetzt." | "Wuerfel 120x90x50. Oben 20mm von vorderer Kante und 15mm aus der Mitte nach links versetzt eine Nut 5x3, 40mm lang entlang X-Achse." |

**Coverage-Check:**
- A1 ✓ (N01, N02, N03, N04, N09, N10, N11, N12)
- A2 ✓ (N05) — forciert edge-to-EDGE auf beiden Achsen
- A3 ✓ (N06, N12)
- A4 ✓ (N06, N08, N11) — pur (N08) + single-axis (N06, N11)
- A6 ✓ (N07)
- B0 ✓ (N08)
- B1 ✓ (N06, N11)
- B2 ✓ (N01, N02, N03, N04, N05, N09, N10)
- B3 ✓ (N12)
- C0 ✓ (N02, N04, N06, N08, N12) — entlang X, kein Drehwinkel
- C1 ✓ (N01, N03, N05, N07, N11) — 90°-Vielfaches (entlang Y/Z oder "parallel zu …")
- C2 ✓ (N09) — CCW +30°
- C3 ✓ (N10) — CW -20°
- D1+D2 pro Test ✓
- Richtungs-Wordings: "entlang Achse" (N01, N02, N04-N12), "verlaeuft nach" (N03), "Anfangs-/Endpunkt" (N04), "parallel zu Kante" (N11)
- Per-Achse-DIN (Length=edge-to-edge, Width=edge-to-center): implizit in N01 (Y-Length: oy=+7), N02 (X-Length: ox=±..), N06, N07, N12

**Seiten-Verteilung:** oben 5x, unten 1x, vorne 2x, hinten 2x, links 1x, rechts 1x → alle 6 Seiten min. 1x.

**Rotation-Edge-Case (Konv. 21 ≠ 90er):** N09 (C2) und N10 (C3) triggern den
Konvention-21-Sonderfall — Length-Achse ist keine reine wx/wy mehr, Resolver
faellt auf konservatives edge-to-CENTER auf beiden Achsen zurueck. Test
prueft, dass Slot innerhalb des Bauteils landet (kein Ueberragen).

## Referenzen

- DIN 406-12 — Maßeintragung in Zeichnungen, Schluessel-Massbezuege
- ISO 5459 — Geometrical Product Specifications, Datums und Datum-Systeme
  (relevant fuer Slot-Centerline-Bezugs-Konvention)

## Stand

Implementiert 2026-05-14 (Commits c5f888d, 4ae367d). Resolver
per-Achse-Logik plus 8 vereinheitlichte Klassifizierer-Demos plus 3
Anti-Ignorieren-Demos im Normalizer (gegen Coin-Flip bei "tasche/nut +
versetzt + zentral" Phrasing).

V2 Real-Pipeline-Run verifiziert: `nut_oben_5: ox=-48.0, oy=+7.0`
deterministisch ueber 5 Folge-Runs (vorher 1/30 Coin-Flip).
