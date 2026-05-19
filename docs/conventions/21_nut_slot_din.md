# 21 — Nut / Slot Bemassung (ISO 129-1, Mittellinien-Bezug)

> Norm-Anker: **DIN EN ISO 129-1:2022-02**. Frueher DIN 406-12 — diese
> ist zurueckgezogen (siehe [`99_normen_audit.md`](99_normen_audit.md)).

## Konvention

Eine Nut/ein Langloch wird ueber ihre **Mittellinie** positioniert — auf
**beiden** Achsen, in **jeder** Rotation. Die Mittellinie ist die
Symmetrieachse des Slots und zugleich die Werkzeug-Bahn; sie ist das
norm-treue Bezugselement (ISO 129-1: bemasst wird zu einem definierten
Geometrieelement — fuer ein symmetrisches Feature ist das die
Mittellinie, analog zur Achse einer Bohrung).

- **Position** = Mittellinie + Mittelpunkt + Winkel.
- `abstand_*` (von der Bauteilkante) → Bauteilkante zur **Slot-
  Mittellinie**, Length- wie Width-Achse gleich. Kein per-Achse-Sonderfall.
- `versatz_*` (aus der Bauteilmitte) → Bauteilmitte zum **Slot-Mittelpunkt**.
- **Rotation** ist kein Sonderfall: Mittelpunkt + Winkel. Eine gedrehte
  Nut hat keine achsparallele Aussenkante — der Mittelpunkt ist ohnehin
  die einzig sinnvolle Referenz.

Die **Slot-Aussenkante / das Slot-Ende** ist **keine** primaere
Positions-Referenz. Die Distanz Slot-Ende → Bauteilkante
(Restwandstaerke) ist ein *sekundaeres Funktionsmass* und wird explizit
ueber `kante_*` (`pocket_edge_distances`, edge-to-EDGE) angegeben — nicht
ueber den `abstand_*`-Default.

### Abgeloeste per-Achse-Regel

Bis 2026-05-18 galt hier eine per-Achse-Regel (Length-Achse edge-to-EDGE
zur Slot-Aussenkante, Width-Achse edge-to-CENTER). Das war ein
Konstrukteurspraxis-Default, der **Positions-** und **Restwandstaerke-**
Bemassung vermischt hat — keine ISO-129-1-Regel (siehe
[`99_normen_audit.md`](99_normen_audit.md)). Ersetzt durch die
einheitliche Mittellinien-Regel oben.

> **Migrations-Status (Stand 2026-05-18, Paket 1 erledigt):**
> Resolver-Slot-per-Achse-Branch entfernt, `_resolve_slot_endpoints` auf
> Mittelwert `(anfang+ende)/2` umgestellt. Resolver-Component-Goldens
> (V2, N_coverage N01-N12, N_kombo) auf Mittellinien-Bezug aktualisiert
> — 303/303 Tests gruen. Offen: Pipeline-Goldens-Heatmap unter
> Mittellinien-Konvention verifizieren (Ollama, separate Sitzung) +
> Spec-Phrasen-Pass wo das Wording mehrdeutig blieb. Endradien-Template
> und Restwandstaerke-Validator bleiben eigene Arbeitspakete.

## Wording-Beispiele

Wuerfel 120x90x50, Nut 5x3 (Width × Tiefe), Laenge 40mm entlang Y-Achse
(angle_deg=90 → wy ist Length-Achse, wx ist Width-Achse):

| Phrase | Klassifizierer-Output | Resolver-Output (Soll) | Geometrie |
|---|---|---|---|
| "von linker Kante 12mm" | `abstand_links: 12` | `ox = -W/2 + 12 = -48` | Mittellinie 12mm vom linken Rand |
| "von oberer Kante 18mm" | `abstand_oben: 18` | `oy = +H/2 - 18 = +27` | Mittellinie 18mm vom oberen Rand |

`abstand_*` referenziert auf **beiden** Achsen die Slot-Mittellinie —
kein per-Achse-Unterschied. Die Slot-`Laenge` geht NICHT in das
Positions-Offset ein (sie ist eine Groesse, kein Bezug).

Nennt die Phrase explizit die Slot-Endkante ("deren obere Endkante 18mm
von oberer Wuerfelkante") → `kante_oben: 18` → `pocket_edge_distances`
(edge-to-EDGE) → der Slot-Endpunkt landet 18mm vom Rand. Das ist der
bewusste Weg fuer eine Restwandstaerke-Bemassung.

## Edge-Cases

### Rotation

Eine gedrehte Nut wird wie jede Nut ueber Mittelpunkt + Winkel
positioniert — die Mittellinien-Regel gilt unveraendert, Rotation ist
**kein Sonderfall**. (Frueher brach die per-Achse-Regel bei ≠90°-Winkeln
zusammen und musste auf edge-to-CENTER zurueckfallen; mit der
Mittellinien-Regel entfaellt diese Sonderbehandlung komplett.)

### Slot mit `pocket_edge_distances` (explizit edge-to-EDGE)

Nennt die Phrase explizit die **Slot-Endkante** / "deren X-Kante",
emittiert der Klassifizierer `kante_*` → `pocket_edge_distances`. Der
Resolver misst dann Bauteilkante → Slot-Aussenkante (edge-to-EDGE) auf
der betroffenen Achse. Das ist der bewusste Weg fuer eine Restwand-
staerke-/Endkanten-Bemassung und ueberschreibt den `abstand_*`-
Mittellinien-Default.

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
`abstand_<kante> = (anfang + ende) / 2` (Mittelpunkt der zwei Endpunkte,
passend zum Mittellinien-Bezug).

### `versatz_*` und `abstand_*` — beide zur Mittellinie

`abstand_*` (von der Bauteilkante) und `versatz_*` (aus der Bauteilmitte)
referenzieren beide den **Nut-Mittelpunkt / die Mittellinie** — auf
beiden Achsen. Sie unterscheiden sich nur im Bezugspunkt (Bauteilkante
vs. Bauteilmitte), nicht in der Slot-Referenz.

Beispiel N12: "Oben eine Nut 5x3, 40mm lang entlang X, von vorderer Kante
20mm **und 15mm aus der Mitte nach links versetzt**":
- `abstand_vorne: 20` → Mittellinie 20mm vom vorderen Rand
- `versatz_links: 15` → Nut-Mittelpunkt 15mm links der Bauteilmitte

Wer den Slot-**Endpunkt** referenzieren will (Restwandstaerke), nennt
die Endkante explizit → `kante_*` (`pocket_edge_distances`, edge-to-EDGE).

## Code-Pfad

- **Klassifizierer:** [`data/prompts/prompt_classifier_slot.py`](../../data/prompts/prompt_classifier_slot.py).
  Default-Regel "von X-Kante Y mm" → `abstand_*`. Explizit "die X-Kante"
  → `kante_*`.
- **Feature-Builder:** [`src/tools/feature_builder.py`](../../src/tools/feature_builder.py)
  `_SLOT_AXIS_TO_ANGLE` Mapping side+axis → angle_deg. Slot-Length aus
  normalisierten Parametern bzw. Anfangs-/Endpunkt-Phrasen.
- **Resolver:** [`src/tools/blueprint_resolver/compose.py`](../../src/tools/blueprint_resolver/compose.py)
  `_compute_offsets` — Slot-per-Achse-Branch entfernt (2026-05-18);
  Slot ist hole-like → `is_box=False` → edge-to-CENTER auf beiden
  Achsen, ohne `child_half`-Abzug, wie bei `hole_single`.
- **Slot-Footprint:** `_get_child_face_size` mit `feat_type="slot"`
  wird fuer `pocket_edge_distances` (explizites edge-to-EDGE) weiter
  gebraucht; fuer den `abstand_*`-Default-Pfad nicht mehr.

## Tests

> **Migrations-Status:** Resolver-Component-Goldens (V2 `slot_top_y_edge`,
> N_coverage N01–N12, N_kombo) wurden 2026-05-18 auf Mittellinien-Bezug
> aktualisiert — 303/303 Tests gruen. Pipeline-Goldens (Full-Ollama-Run)
> stehen noch aus; Spec-Texte (D1/D2) sind grossteils weiter gueltig,
> mehrdeutige Stellen ("von oberer Kante 18mm") werden mit dem Heatmap-
> Lauf re-verifiziert.

### Bestehende Tests (Stand pre-Coverage-Matrix)

- Unit: [`tests/tools/test_kante_vs_abstand.py`](../../tests/tools/test_kante_vs_abstand.py)
  `test_kante_top_left_on_y_slot_uses_width_and_length` — explizite
  `pocket_edge_distances` bei Slot; Slot-Footprint aus `length`/`width`
  wird fuer edge-to-EDGE korrekt genutzt.
- Component-Goldens: [`tests/golden/components/N_kombo_basics/`](../../tests/golden/components/N_kombo_basics/)
  `nut_kanten_top30_left20_y_l40` — `abstand_*` nach Mittellinien-
  Konvention (ox=-30, oy=+20).
- Pipeline-Goldens: [`tests/golden/components/V2_balanced_feature_palette/`](../../tests/golden/components/V2_balanced_feature_palette/)
  `slot_top_y_edge` — Real-Pipeline-Verifikation, ox=-48, oy=+27
  nach Mittellinien-Bezug.
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
- Mittellinien-Bezug (beide Achsen edge-to-center): N01-N12 (Soll-`offset`-Werte werden im Golden-Rework angepasst — siehe Migrations-Hinweis oben)

**Seiten-Verteilung:** oben 5x, unten 1x, vorne 2x, hinten 2x, links 1x, rechts 1x → alle 6 Seiten min. 1x.

**Rotation (N09 C2, N10 C3):** Mit der Mittellinien-Regel ist Rotation
kein Sonderfall — Mittelpunkt + Winkel, edge-to-center wie bei jedem
Slot. Test prueft weiterhin, dass der Slot innerhalb des Bauteils landet
(kein Ueberragen).

## Offene Luecken (Stand 2026-05-18 — erledigt)

- ✅ **Endradien:** Slot-Template rendert seit 2026-05-18 immer
  `.slot2D(length, width, angle)` mit halbrunden Enden (`R = width/2`).
  Vor 2026-05-18 nutzte der gerade Pfad `.rect()` (alte edge-to-edge-
  Konvention).
- ✅ **Restwandstaerken-Pruefung:** `coordinate_validator.py` Check 11
  (`_check_slot_min_clearance`) emittiert WARNING wenn die Slot-Aussen-
  kontur (length×width-AABB, angle-rotiert) naeher als 0.5mm an einer
  Bauteilkante liegt. Negative Werte = Ueberhang. Schwellwert ueber
  `_MIN_SLOT_REST_WALL_MM` konfigurierbar.

## Referenzen

- **DIN EN ISO 129-1:2022-02** — Eintragung von Massen und Toleranzen
  (Primaer-Anker; loest die zurueckgezogene DIN 406-12 ab).
- **DIN EN ISO 5459:2025-12** — Datums und Datum-Systeme (relevant sobald
  Slot-Position toleranzbehaftet auf ein Datum bezogen wird, Cap 7.0).
- DIN 406-12 — historisch, zurueckgezogen.

## Stand

Mittellinien-Bezug als Konvention seit 2026-05-18 (Schritt 3 Konventions-
Audit). Die fruehere per-Achse-Regel (implementiert 2026-05-14, Commits
c5f888d / 4ae367d) ist abgeloest; Code, Component-Goldens,
Slot-Template-Endradien und Restwandstaerke-Validator sind migriert.
