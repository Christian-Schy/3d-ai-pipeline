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

### A5 — Anchor + Versatz: **nicht anwendbar fuer Bohrung**

Bohrungen sind **point-like** — sie haben keine eigene Ecke, die mit einer
Bauteil-Face-Ecke korrespondieren koennte. Phrasen wie "in der oberen
rechten Ecke 8mm nach links und 6mm nach unten" sind **mathematisch
identisch** zu A1 mit den entsprechenden Edge-Distanzen (z.B.
`abstand_rechts: 8` + `abstand_oben: 6`). Konstrukteur-Wording fuer
Bohrungen folgt daher A1, nicht A5.

Das deckt sich mit der Ecken-Regel in
[`10_masseintragung_din406.md`](10_masseintragung_din406.md): eine Eck-
Phrase = zwei `abstand_*`-Kantenmasse, kein eigener Anchor-Typ. (Die
Coverage-Matrix listet Bohrung-A5 noch als Pflicht — das ist ein
Matrix-Fehler, wird in Schritt `11` bereinigt.)

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
- **Resolver:** [`src/tools/blueprint_resolver/compose.py`](../../src/tools/blueprint_resolver/compose.py)
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
| **H08** | unten | A1+A4, B1 | "Wuerfel 100x80x40. Unten eine Bohrung Ø6 Tiefe 12, mittig in der Breite und 30mm von der vorderen Kante." | "Wuerfel 100x80x40. Unten mittig in der Breite und 30mm von der vorderen Kante eine Bohrung Ø6 Tiefe 12." |
| **H09** | hinten | A3+A4, B1 | "Wuerfel 100x80x40. Hinten eine Bohrung Ø8 Tiefe 12, mittig in der Breite und 12mm aus Mitte nach oben." | "Wuerfel 100x80x40. Hinten mittig in der Breite und 12mm aus der Mitte nach oben eine Bohrung Ø8 Tiefe 12." |
| **H10** | oben | A4+A3, B3 | "Wuerfel 100x80x40. Oben eine Bohrung Ø6 Tiefe 10, mittig auf der Y-Achse und 20mm aus Mitte nach rechts." | "Wuerfel 100x80x40. Oben mittig auf der Y-Achse und 20mm aus der Mitte nach rechts eine Bohrung Ø6 Tiefe 10." |

**Coverage-Check:**
- A1 ✓ (H01, H03, H04, H06, H08) — alle 6 Seiten abgedeckt via H01-H10
- A3 ✓ (H02, H03, H09, H10)
- A4 ✓ (H04, H05, H08, H09, H10) — sowohl pur als auch single-axis
- A5 nicht anwendbar (point-like Feature — siehe A5-Sektion oben)
- A6 ✓ (H06)
- B1 ✓ (H04, H05, H08, H09)
- B2 ✓ (H01, H02, H06)
- B3 ✓ (H03, H10)
- D1+D2 pro Test ✓

**Seiten-Verteilung:** oben 2x, unten 2x, vorne 1x, hinten 2x, links 1x, rechts 1x → alle 6 Seiten min. 1x.

## Referenzen

- **DIN EN ISO 129-1:2022-02** — Eintragung von Massen und Toleranzen
  (Primaer-Anker; loest die zurueckgezogene DIN 406 ab).
- **DIN EN ISO 128-Reihe** — Schnitt-/Ansichtsdarstellung (loest die
  zurueckgezogene DIN 6 ab).
- DIN 406 / DIN 6 — historisch, zurueckgezogen (siehe
  [`99_normen_audit.md`](99_normen_audit.md)).
- Verkn. Konvention: [`10_masseintragung_din406.md`](10_masseintragung_din406.md),
  Coverage-Schema: [`11_coverage_matrix.md`](11_coverage_matrix.md)

## Stand

Coverage-Matrix-abgeleitete Test-Liste (9 Spec-Paare = 18 Test-Cases) —
Pilot fuer 22/21/24/25. A5 entfaellt fuer point-like Bohrung. Resolved-Blueprints werden pro Test ausgefuellt
sobald User-Review der Spec-Wordings abgeschlossen ist.
