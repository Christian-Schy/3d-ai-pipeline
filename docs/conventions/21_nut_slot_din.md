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
Forderung "die Slot-Kante exakt X mm vom Rand". Das LLM uebergibt
beide Felder; der Resolver `pocket_edge_distances`-Pfad ueberschreibt
die Default-Slot-Per-Achse-Logik.

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
