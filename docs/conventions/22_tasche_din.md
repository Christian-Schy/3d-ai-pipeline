# 22 — Tasche / Pocket (DIN-Bemassung, Coverage-Matrix-abgeleitet)

## Konvention

Taschen sind **rechteckige subtractive Features mit eigener Außenkante**.
Sie nutzen die **volle** DIN-Bezugs-Methodik aus
[`10_masseintragung_din406.md`](10_masseintragung_din406.md):

- **A1 (`abstand_*`)** edge-to-CENTER — Default. Bauteilkante → Pocket-Center.
- **A2 (`kante_*`)** edge-to-EDGE — explizit, wenn die Phrase eine
  **Feature-Kante** der Tasche nennt. Pocket-Außenkante → Bauteilkante.
- **A3 (`versatz_*`)** center-relativ aus der Face-Mitte.
- **A4** alignment (centered / flush).
- **A5 (= A1)** — Eck-Phrase ("in der oberen rechten Ecke der Face,
  X nach links, Y nach unten") ist numerisch A1 mit zwei `abstand_*`-
  Werten (Ecken-Regel aus
  [`10_masseintragung_din406.md`](10_masseintragung_din406.md)). Kein
  eigenes Anker-Schema fuer Eck-Phrasen. Details siehe A5-Sektion unten.
- **A6** "jeweils"-Regel (zwei Bauteilkanten gleich weit).
- **C0/C2/C3** Rotation 0° / CCW / CW.

Relevante Matrix-Zellen (siehe [`11_coverage_matrix.md`](11_coverage_matrix.md)):
**A1, A2, A3, A4, A5, A6** × **B0, B1, B2, B3** × **C0, C2, C3** × **D1, D2**.

## Wording-Beispiele

(Auszug — voller Wording-Pool in [`11_coverage_matrix.md`](11_coverage_matrix.md)
"Eigene Wording-Beispiele".)

### A1 — `abstand_*` (Bauteilkante → Pocket-Center)

| Phrase | Interpretation |
|---|---|
| "von linker Kante 15mm und von vorderer Kante 25mm" | Pocket-Center bei (-W/2+15, -H/2+25) auf Top-Face |
| "20mm von der unteren Kante entfernt" | Pocket-Center 20mm vom unteren Rand |

### A2 — `kante_*` (Pocket-Außenkante → Bauteilkante)

| Phrase | Interpretation |
|---|---|
| "die linke Taschen-Kante 12mm vom linken Rand" | Pocket-Left-Edge 12mm vom Bauteil-Left, Pocket-Center = -W/2 + 12 + L/2 |
| "die rechte Taschen-Kante 20mm vom rechten Rand und die obere Taschen-Kante 15mm vom oberen Rand" | beide Pocket-Edges auf Distanz |
| "obere rechte Ecke der Tasche soll von oben 10mm und von rechts 20mm entfernt sein" | Feature-Ecke = 2 Feature-Kanten gleichzeitig, behandelt als A2-dual |

### A3 — `versatz_*`

| Phrase | Interpretation |
|---|---|
| "von der Mitte um 10mm nach rechts und 15mm nach hinten versetzt" | Pocket-Center bei (+10, +15) auf Face |
| "30mm Versatz nach unten von der Mitte" | nur Y-Achse, X bleibt zentriert (B1) |

### A4 — alignment

| Phrase | Interpretation |
|---|---|
| "zentriert" / "mittig" | beide Achsen alignment=centered (B0) |
| "mittig auf der Hoehe" | nur Y-Achse zentriert (B1-Komponente) |
| "rechtsbuendig anliegend" | alignment=flush_right (0 Offset, **kein** Distanz-Mass!) |

### A5 — Face-Ecke + Versatz = A1

| Phrase | Interpretation |
|---|---|
| "in der oberen rechten Ecke, 22mm nach links und 18mm nach unten versetzt" | `abstand_rechts:22, abstand_oben:18` (Zentrum von rechter + oberer Kante) |

A5 ist **kein eigener Fall**. Eine Ecke nennt zwei Kanten; der Versatz
bemasst — Default-Konvention A1, edge-to-CENTER — das Tasche-ZENTRUM von
genau diesen zwei Kanten. "In der oberen rechten Ecke, X nach links,
Y nach unten" = `abstand_rechts:X, abstand_oben:Y`. Kein `anker_ecke`,
kein Anker-Schema.

**Hinweis:** Phrasen wie "obere rechte Ecke **der Tasche**" sind A2
(edge-to-edge, `kante_*`) — dort ist die *Taschen-Kante* explizit
genannt. "In der Ecke" ohne genannte Taschen-Kante bleibt A1.

### A6 — "jeweils"

| Phrase | Interpretation |
|---|---|
| "jeweils 12mm von linker und vorderer Kante" | abstand_links=12 + abstand_vorne=12 |

### C2/C3 — Rotation

| Phrase | rotation_deg |
|---|---|
| "um 30° gedreht" (Default = CCW) | +30 |
| "um 20° im Uhrzeigersinn gedreht" | -20 |
| "soll eine Rotation um 10° im Uhrzeigersinn haben" | -10 |

## Edge-Cases

### Tasche ueberragt das Bauteil

Bei A1 (`abstand_*`) kann die Pocket-Außenkante das Bauteil ueberragen, wenn
die Distanz kleiner als `pocket_half` ist. Beispiel: Tasche 25x25 unten,
`abstand_vorne: 8` → Pocket-Front-Edge bei -45 + 8 = -37, dann -12.5 → -49.5,
also 4.5mm außerhalb. Wenn das **gewollt** ist (z.B. seitlich offene
Tasche), soll die User-Spec das explizit sagen ("ragt 5mm ueber den Rand").
Wenn das **unerwollt** ist, sollte die Phrase A2 (`kante_*`) verwenden
("die vordere Taschen-Kante 8mm vom vorderen Rand") — dann passt's.

Der `coordinate_validator` ([`src/tools/coordinate_validator.py`](../../src/tools/coordinate_validator.py))
warnt deterministisch bei pocket-ueberragt. Aktuelle Behandlung: nur
Warning, nicht harter Fehler — der User darf das wollen.

### A2 mit Distanz=0 = A4 flush

Wenn der Klassifizierer `kante_rechts: 0` emittiert, normalisiert der
Resolver das auf `alignment: flush_right`. "anliegend X mm" ohne Zahl X
gibt es nicht — bündig **schließt Offset aus**.

### Rotation ohne explizite Bauteil-Bezugskante

Bei C2/C3 (rotiert ≠ 0°) berechnet der Resolver den Pocket-Footprint nach
Rotation. `coordinate_validator._check_offset_bounds` prueft den
Ueberhang seit 2026-05-18 mit der echten **rotierten AABB**
(`x_half·|cos θ| + y_half·|sin θ|`), nicht mehr mit axis-aligned `x/2`.
Damit faengt der Validator vorher uebersehene Ueberhaenge — die alte
"bbox-Approximation" Limitation ist behoben.

### "obere Kante der Tasche" auf horizontaler Face

Auf einer Top-Face hat die Tasche nur 4 In-Plane-Außenkanten (links/rechts/
vorne/hinten) — keine "obere Kante" (die waere der Pocket-Boden, also
Z-Tiefe, nicht A2). Klassifizierer sollte "obere Kante der Tasche" nur
auf Side-Faces (vorne/hinten/links/rechts) als A2 akzeptieren.

## Code-Pfad

- **Klassifizierer:** [`data/prompts/prompt_classifier_pocket.py`](../../data/prompts/prompt_classifier_pocket.py)
  — Default A1, A2 bei expliziter Feature-Kante, A3 bei expliziter "Mitte"-Phrase.
  **TODO:** Trigger-Regel fuer A2 ohne "deren" + explizite A3-Regel ergaenzen.
- **Feature-Builder:** [`src/tools/feature_builder.py`](../../src/tools/feature_builder.py)
  `_extract_edge_distances` / `_extract_pocket_edge_distances` / `_extract_center_offset`.
- **Resolver:** [`src/tools/blueprint_resolver.py`](../../src/tools/blueprint_resolver.py)
  `_compute_offsets` Branch fuer `pocket_rect` — `pocket_edge_distances`
  subtrahiert `pocket_half` von der Distanz, edge-to-edge wird zu
  edge-to-center umgerechnet.
- **Templates:** [`src/codegen/templates.py`](../../src/codegen/templates.py)
  `pocket_rect`-Template mit Rotation.

## Tests — Coverage-Matrix-abgeleitet

Bauteil fuer alle Tests: **Wuerfel 120x90x50** (X x Y x Z).
Pro Test pflegen wir **D1** + **D2** (Feature-zuerst / Position-zuerst).
Resolved-Blueprint identisch fuer das D1/D2-Paar.

| ID | Face | Matrix-Zellen | D1 (Feature → Position) | D2 (Position → Feature) |
|---|---|---|---|---|
| **T01** | oben | A1, B2, C0 | "Wuerfel 120x90x50. Auf der Oberseite eine Tasche 30x20x10, von linker Kante 15mm und von vorderer Kante 25mm entfernt." | "Wuerfel 120x90x50. Oben 15mm von der linken Kante und 25mm von der vorderen Kante eine Tasche 30x20x10." |
| **T02** | vorne | A2, B2, C0 | "Wuerfel 120x90x50. Vorne eine Tasche 25x18x8, die linke Taschen-Kante 12mm vom linken Rand und die untere Taschen-Kante 15mm vom unteren Rand." | "Wuerfel 120x90x50. Vorne, mit der linken Taschen-Kante 12mm vom linken Rand und der unteren Taschen-Kante 15mm vom unteren Rand, eine Tasche 25x18x8." |
| **T03** | unten | A3, B2, C0 | "Wuerfel 120x90x50. Unten eine Tasche 30x25x6, von der Mitte um 10mm nach rechts und 15mm nach hinten versetzt." | "Wuerfel 120x90x50. Unten 10mm aus der Mitte nach rechts und 15mm nach hinten versetzt eine Tasche 30x25x6." |
| **T04** | hinten | A4, B0, C0 | "Wuerfel 120x90x50. Hinten eine zentrierte Tasche 50x30x8." | "Wuerfel 120x90x50. Hinten zentriert eine Tasche 50x30x8." |
| **T05** | links | A1+A4, B1, C0 | "Wuerfel 120x90x50. Links eine Tasche 25x18x10, mittig auf der Hoehe und von rechter Kante 20mm." *(face-local: rechte Kante der Left-Face)* | "Wuerfel 120x90x50. Links mittig auf der Hoehe und 20mm von rechter Kante eine Tasche 25x18x10." |
| **T06** | rechts | A2+A1, B3, C0 | "Wuerfel 120x90x50. Rechts eine Tasche 20x15x8, die obere Taschen-Kante 10mm vom oberen Rand und von linker Kante 18mm." *(face-local: linke Kante der Right-Face)* | "Wuerfel 120x90x50. Rechts mit der oberen Taschen-Kante 10mm vom oberen Rand und 18mm von linker Kante eine Tasche 20x15x8." |
| **T07** | oben | A6, C0 | "Wuerfel 120x90x50. Oben eine Tasche 30x20x10 jeweils 12mm von linker und vorderer Kante." | "Wuerfel 120x90x50. Oben jeweils 12mm von linker und vorderer Kante eine Tasche 30x20x10." |
| **T08** | unten | A5 (=A1), C0 | "Wuerfel 120x90x50. Unten eine Tasche 25x18x6, in der oberen rechten Ecke, 22mm nach links und 18mm nach unten versetzt." | "Wuerfel 120x90x50. Unten in der oberen rechten Ecke der Face 22mm nach links und 18mm nach unten versetzt eine Tasche 25x18x6." |
| **T09** | oben | A1+A3, B3, C0 | "Wuerfel 120x90x50. Oben eine Tasche 25x20x8, von linker Kante 25mm und 10mm aus Mitte nach hinten versetzt." | "Wuerfel 120x90x50. Oben 25mm von der linken Kante und 10mm aus der Mitte nach hinten versetzt eine Tasche 25x20x8." |
| **T10** | oben | A1, B2, **C2** | "Wuerfel 120x90x50. Oben eine Tasche 30x15x8, um 30° gedreht, von linker Kante 40mm und von vorderer Kante 30mm." | "Wuerfel 120x90x50. Oben 40mm von linker Kante und 30mm von vorderer Kante eine um 30° gedrehte Tasche 30x15x8." |
| **T11** | oben | A4, B0, **C3** | "Wuerfel 120x90x50. Oben eine zentrierte Tasche 25x18x10, um 20° im Uhrzeigersinn gedreht." | "Wuerfel 120x90x50. Oben zentriert eine um 20° im Uhrzeigersinn gedrehte Tasche 25x18x10." |
| **T12** | vorne | A4+A1, B1, C0 | "Wuerfel 120x90x50. Vorne eine Tasche 25x18x8, oben buendig anliegend und 20mm von der rechten Kante." | "Wuerfel 120x90x50. Vorne oben buendig anliegend und 20mm von der rechten Kante eine Tasche 25x18x8." |

**Coverage-Check:**
- A1 ✓ (T01, T05, T06, T07, T09, T10, T12)
- A2 ✓ (T02, T06)
- A3 ✓ (T03, T09)
- A4 ✓ (T04, T05, T11, T12) — pur (T04, T11) + single-axis (T05, T12)
- A5 ✓ (T08)
- A6 ✓ (T07)
- B0 ✓ (T04, T11)
- B1 ✓ (T05, T12)
- B2 ✓ (T01, T02, T03, T10)
- B3 ✓ (T06, T09)
- C0 ✓ (T01-T09, T12) — Default
- C2 ✓ (T10) — CCW
- C3 ✓ (T11) — CW
- D1+D2 pro Test ✓

**Seiten-Verteilung:** oben 5x, unten 2x, vorne 2x, hinten 1x, links 1x, rechts 1x → alle 6 Seiten min. 1x.

## Referenzen

- **DIN EN ISO 129-1:2022-02** — Eintragung von Massen und Toleranzen
  (Primaer-Anker; loest die zurueckgezogene DIN 406 ab).
- DIN 406 — historisch, zurueckgezogen (siehe
  [`99_normen_audit.md`](99_normen_audit.md)).
- Verkn. Konventionen: [`10_masseintragung_din406.md`](10_masseintragung_din406.md),
  [`11_coverage_matrix.md`](11_coverage_matrix.md), [`20_bohrung_din.md`](20_bohrung_din.md)

## Stand

Coverage-Matrix-abgeleitete Test-Liste (12 Spec-Paare = 24 Test-Cases) —
analog zu Bohrung-Pilot. Resolved-Blueprints werden pro Test ausgefuellt
sobald User-Review der Spec-Wordings abgeschlossen ist.
