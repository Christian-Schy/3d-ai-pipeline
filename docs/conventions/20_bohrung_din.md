# 20 — Bohrung (DIN-Bemassung, Coverage-Matrix-abgeleitet)

## Konvention

Bohrungen sind **point-like** — sie haben keine eigene Kante, sondern nur
einen Mittelpunkt. Daraus folgt:

- **Default**: edge-to-CENTER (`abstand_*`) — Bauteilkante → Bohrungs-Center.
- **`kante_*` ist semantisch unsinnig** und wird im Feature-Builder
  ([`src/tools/feature_builder.py`](../../src/tools/feature_builder.py)
  `_extract_pocket_edge_distances` + Re-Routing `_POCKET_EDGE_TYPES`)
  auf `edge_distances` umgeroutet, falls das LLM es dennoch emittiert.
- **Keine Rotation** — zylindrische Symmetrie um die Bohrungsachse.

Relevante Matrix-Zellen (siehe [`11_coverage_matrix.md`](11_coverage_matrix.md)):
**A1, A3, A4, A5, A6** × **B1, B2, B3** × **C0** × **D1, D2**.

## Wording-Beispiele

### A1 — `abstand_*` (edge-to-CENTER)

| Phrase | Interpretation |
|---|---|
| "von linker Kante 25mm" | Bohrungs-Center 25mm vom linken Wuerfelrand |
| "von oberer Kante 18mm" | Bohrungs-Center 18mm vom oberen Wuerfelrand |
| "jeweils 15mm von linker und unterer Kante" | abstand_links=15 + abstand_unten=15 |

### A3 — `versatz_*` (center-relativ)

| Phrase | Interpretation |
|---|---|
| "10mm aus Mitte nach rechts" | Bohrungs-Center bei (+10, 0) auf der Face |
| "5mm aus der Mitte nach oben" | Bohrungs-Center bei (0, +5) auf der Face |
| "10mm aus Mitte nach rechts und 8mm aus Mitte nach oben" | Combined (+10, +8) |

### A4 — `alignment`

| Phrase | Interpretation |
|---|---|
| "zentriert", "mittig" | alignment=centered (beide Achsen) |
| "mittig auf der Hoehe" | nur Hoehen-Achse zentriert |
| "mittig in der Breite" | nur Breiten-Achse zentriert |

### A5 — Anchor + Versatz

| Phrase | Interpretation |
|---|---|
| "in der oberen rechten Ecke" | anchor=top_right |
| "obere rechte Ecke, 8mm nach links und 6mm nach unten versetzt" | anchor=top_right + offset {left:8, down:6} |

### A6 — "jeweils"

"jeweils X mm von ..." setzt X auf **beide** in der Phrase genannten Kanten.

## Edge-Cases

### "kante_*" auf Bohrung leakt aus LLM

Wenn das LLM trotz Prompt-Verbot `kante_*` emittiert, route der
Feature-Builder es nach `abstand_*` um (siehe Re-Routing-Code).
Begruendung: ein Punkt hat keine "linke Kante" — der Konstrukteur
meinte trotzdem den Center-Abstand. Run `bc28acc5` zeigte den Fix
(vorher: offset_y=81 statt 90 wegen child_half-Subtraktion).

### Mehrere Side-Woerter ohne klare Trennung

"Vorne rechts oben" — das erste bare Side-Wort ist die Face-Auswahl
(`vorne`), die folgenden sind Positionen auf dieser Face. Siehe
`prompt_classifier_hole.py` "Mehrere Side-Woerter"-Regel.

### Doppel-Versatz-Mehrdeutigkeit auf Side-Faces

Auf Side-Faces (rechts/links/vorne/hinten) **nicht** "nach oben" + "nach
hinten" in derselben Phrase, weil das User-Mental-Modell (2D-Bildschirm:
"hinten" = "oben auf Bildschirm") die beiden visuell auf dieselbe
Richtung legt. Loesung: ein `versatz_*` + ein `abstand_*` pro
Side-Face-Spec, **nicht** zwei `versatz_*`.

## Code-Pfad

- **Klassifizierer:** [`data/prompts/prompt_classifier_hole.py`](../../data/prompts/prompt_classifier_hole.py)
- **Feature-Builder:** [`src/tools/feature_builder.py`](../../src/tools/feature_builder.py)
  `_extract_edge_distances` / `_extract_center_offset` / Re-Routing fuer
  `_POCKET_EDGE_TYPES`-Ausschluss.
- **Resolver:** [`src/tools/blueprint_resolver.py`](../../src/tools/blueprint_resolver.py)
  `_compute_offsets` Branch fuer `hole_single` (point-like, kein
  child_half-Subtract).

## Tests — Coverage-Matrix-abgeleitet

Bauteil fuer alle Tests: **Wuerfel 100x80x40** (X x Y x Z).
Pro Test pflegen wir **D1** + **D2** (Feature-zuerst / Position-zuerst).
Resolved-Blueprint identisch fuer das D1/D2-Paar.

| ID | Face | Matrix-Zellen | D1 (Feature → Position) | D2 (Position → Feature) |
|---|---|---|---|---|
| **H01** | oben | A1, B2 | "Wuerfel 100x80x40. Oben eine Bohrung Ø8 Tiefe 20, von linker Kante 25mm und von vorderer Kante 20mm." | "Wuerfel 100x80x40. Oben 25mm von der linken Kante und 20mm von der vorderen Kante eine Bohrung Ø8 Tiefe 20." |
| **H02** | vorne | A3, B2 | "Wuerfel 100x80x40. Vorne eine Bohrung Ø6 Tiefe 15, 10mm aus Mitte nach rechts und 8mm aus Mitte nach oben." | "Wuerfel 100x80x40. Vorne 10mm aus der Mitte nach rechts und 8mm aus der Mitte nach oben eine Bohrung Ø6 Tiefe 15." |
| **H03** | unten | A1+A3, B3 | "Wuerfel 100x80x40. Unten eine Bohrung Ø10 Tiefe 12, von linker Kante 20mm und 15mm aus Mitte nach hinten." | "Wuerfel 100x80x40. Unten von linker Kante 20mm und 15mm aus der Mitte nach hinten eine Bohrung Ø10 Tiefe 12." |
| **H04** | hinten | A4+A1, B1 | "Wuerfel 100x80x40. Hinten eine Bohrung Ø8 Tiefe 16, mittig auf der Hoehe und von rechter Kante 20mm." | "Wuerfel 100x80x40. Hinten mittig auf der Hoehe und 20mm von der rechten Kante eine Bohrung Ø8 Tiefe 16." |
| **H05** | links | A4 (pur) | "Wuerfel 100x80x40. Links eine zentrierte Bohrung Ø12 Tiefe 20." | "Wuerfel 100x80x40. Links zentriert eine Bohrung Ø12 Tiefe 20." |
| **H06** | rechts | A6 | "Wuerfel 100x80x40. Rechts eine Bohrung Ø10 Tiefe 12, jeweils 15mm von oberer und rechter Kante." | "Wuerfel 100x80x40. Rechts jeweils 15mm von oberer und rechter Kante eine Bohrung Ø10 Tiefe 12." |
| **H07** | oben | A5 | "Wuerfel 100x80x40. Oben in der oberen rechten Ecke eine Bohrung Ø5 Tiefe 10, 8mm nach links und 6mm nach unten versetzt." | "Wuerfel 100x80x40. Oben 8mm nach links und 6mm nach unten aus der oberen rechten Ecke eine Bohrung Ø5 Tiefe 10." |
| **H08** | unten | A1+A4, B1 | "Wuerfel 100x80x40. Unten eine Bohrung Ø6 Tiefe 12, mittig in der Breite und 30mm von der vorderen Kante." | "Wuerfel 100x80x40. Unten mittig in der Breite und 30mm von der vorderen Kante eine Bohrung Ø6 Tiefe 12." |
| **H09** | hinten | A3+A4, B1 | "Wuerfel 100x80x40. Hinten eine Bohrung Ø8 Tiefe 12, mittig in der Breite und 12mm aus Mitte nach oben." | "Wuerfel 100x80x40. Hinten mittig in der Breite und 12mm aus der Mitte nach oben eine Bohrung Ø8 Tiefe 12." |
| **H10** | oben | A4+A3, B3 | "Wuerfel 100x80x40. Oben eine Bohrung Ø6 Tiefe 10, mittig auf der Y-Achse und 20mm aus Mitte nach rechts." | "Wuerfel 100x80x40. Oben mittig auf der Y-Achse und 20mm aus der Mitte nach rechts eine Bohrung Ø6 Tiefe 10." |

**Coverage-Check:**
- A1 ✓ (H01, H03, H04, H06, H08) — alle 6 Seiten abgedeckt: oben/unten/vorne/hinten/links/rechts via H01-H10
- A3 ✓ (H02, H03, H07, H09, H10)
- A4 ✓ (H04, H05, H08, H09, H10) — sowohl pur als auch single-axis
- A5 ✓ (H07)
- A6 ✓ (H06)
- B1 ✓ (H04, H05, H08, H09)
- B2 ✓ (H01, H02, H06)
- B3 ✓ (H03, H10)
- D1+D2 pro Test ✓

**Seiten-Verteilung:** oben 3x, unten 2x, vorne 1x, hinten 2x, links 1x, rechts 1x → alle 6 Seiten min. 1x.

## Referenzen

- DIN 406 — Maßeintragung in Zeichnungen
- ISO 129-1 — Eintragung von Maßen und Toleranzen
- DIN 6 — Schnittdarstellung
- Verkn. Konvention: [`10_masseintragung_din406.md`](10_masseintragung_din406.md),
  Coverage-Schema: [`11_coverage_matrix.md`](11_coverage_matrix.md)

## Stand

Coverage-Matrix-abgeleitete Test-Liste (10 Spec-Paare = 20 Test-Cases) —
Pilot fuer 22/21/24/25. Resolved-Blueprints werden pro Test ausgefuellt
sobald User-Review der Spec-Wordings abgeschlossen ist.
