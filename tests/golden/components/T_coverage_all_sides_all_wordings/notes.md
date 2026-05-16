# T_coverage_all_sides_all_wordings — Tasche L2-Coverage-Golden

**Capability 1.0 — Tasche/Pocket. Cov-3-Stufe ([CLAUDE.md](../../../../CLAUDE.md)
"L2-Coverage-Goldens").**

Eine Capability komplett: alle 6 Seiten + DIN-Wording-Varianten
A1-A6 × B0-B3 × C0/C2/C3 auf einem **Wuerfel 120x90x50**.

## Test-Faelle (aus [`docs/conventions/22_tasche_din.md`](../../../../docs/conventions/22_tasche_din.md))

9 stabile Taschen — T01-T05, T07, T09-T11. T06/T08/T12 deferred (siehe unten).

| Feature | Face | Matrix-Zellen | DIN-Bezug |
|---|---|---|---|
| `t01_oben_a1_b2` | oben | A1, B2 | edge-to-CENTER, beide Achsen |
| `t02_vorne_a2_b2` | vorne | A2, B2 | edge-to-EDGE (Pocket-Kante), beide Achsen |
| `t03_unten_a3_b2` | unten | A3, B2 | center-offset, beide Achsen |
| `t04_hinten_a4_b0` | hinten | A4, B0 | reines zentriert |
| `t05_links_a1_a4_b1` | links | A1+A4, B1 | single-axis edge-distance |
| `t07_oben_a6` | oben | A6 | "jeweils X von zwei Kanten" |
| `t09_oben_a1_a3_b3` | oben | A1+A3, B3 | edge-distance + center-offset |
| `t10_oben_a1_b2_c2` | oben | A1, B2, **C2** | edge-to-CENTER + Rotation CCW +30 |
| `t11_oben_a4_b0_c3` | oben | A4, B0, **C3** | zentriert + Rotation CW -20 |

**Coverage-Check:**
- A1 ✓ (T01, T05, T09, T10)
- A2 ✓ (T02) — `pocket_edge_distances` edge-to-EDGE
- A3 ✓ (T03, T09)
- A4 ✓ (T04, T05, T11) — pur + single-axis
- A6 ✓ (T07)
- B0 ✓ (T04, T11)
- B1 ✓ (T05)
- B2 ✓ (T01, T02, T03, T10)
- B3 ✓ (T09)
- C0 ✓ (T01-T05, T07, T09) — Default
- C2 ✓ (T10) — CCW +30°
- C3 ✓ (T11) — CW -20°
- **5 von 6 Seiten:** oben (T01, T07, T09, T10, T11), unten (T03), vorne
  (T02), hinten (T04), links (T05). **rechts** nur via T06 (deferred) —
  Resolver-Pfad fuer `>X` ist aber durch B_coverage h06 + N/M-Goldens
  abgedeckt.

## Bekannte Limitierungen — 3 deferred Cases

Drei Faelle aus der Konvention 22 sind aus dem **Pipeline**-Golden
ausgelassen. Alle drei bleiben gueltige Konventions-Bestandteile —
ihre Resolver-Mathe ist korrekt, der LLM-Pfad ist (noch) nicht stabil.

- **T08 (A5 Pocket-Anker)** — `pocket_classifier` hat kein Anker-Konzept
  im Schema. Anders als bei Bohrung ist A5 fuer Tasche valide (Pocket
  hat eigene Ecke). Braucht Klassifizierer-Schema-Erweiterung.
- **T06 (A2+A1 Mischfall)** — "obere Taschen-Kante 10mm vom oberen Rand
  UND von linker Kante 18mm". Der Klassifizierer routet die A1-Phrase
  "von linker Kante" flaky mal als A1 (edge-to-center), mal als A2
  (`kante_*`, edge-to-edge). 2/3 Runs falsch. Konvention 22 Code-Pfad
  flaggt das bereits als TODO ("A2-Trigger-Regel ohne 'deren'").
- **T12 (flush+A1 Mischfall)** — "oben buendig anliegend und 20mm von
  der rechten Kante". Alignment-Klassifikation flaky (flush_top vs
  zentriert). 1/3 Runs falsch.

Sobald die Klassifizierer-Stabilitaet fuer A2/A1-Disambiguierung +
flush+offset verbessert ist (Demos/Prompt), kommen T06/T12 zurueck;
T08 nach Anker-Schema-Erweiterung.

## Resolver-Mathe

Wuerfel 120x90x50 → Face-Half:
- `>Z` / `<Z` (oben/unten): face_w=120, face_h=90 → Half (60, 45)
- `>Y` / `<Y` (hinten/vorne): face_w=120, face_h=50 → Half (60, 25)
- `>X` / `<X` (rechts/links): face_w=90, face_h=50 → Half (45, 25)

Beispiel T02 (vorne, A2 edge-to-EDGE): Pocket 25x18 auf `<Y`,
`pocket_edge_distances {left: 12, bottom: 15}`:
- `left`: ox = -(60 - 12 - 25/2) = **-35.5** (Pocket-Aussenkante 12mm vom Rand)
- `bottom`: oy = -(25 - 15 - 18/2) = **-1.0**

Beispiel T01 (oben, A1 edge-to-CENTER): `edge_distances {left: 15, vorne: 25}`:
- `left`: ox = -(60 - 15) = **-45** (Pocket-Center 15mm vom Rand)
- `vorne`: oy = -(45 - 25) = **-20**

## Was dieser Test absichert

- Klassifizierer-Pfad fuer Tasche auf 5 von 6 Seiten
- A1 (edge-to-CENTER) vs A2 (edge-to-EDGE, Pocket-Kante) als Reinformen
- Pocket-Rotation C2/C3
- Resolver-Math fuer `pocket_edge_distances` (child_half-Subtraktion)
- Multi-Feature-Aggregation auf einem Bauteil

## Naechste L2-Goldens (Plan)

- `N_coverage_all_sides_all_orientations` (Slots/Nuten, N01-N12)
- `M_coverage_patterns_all_kinds` (Grid/Kreis/Linear, M01-M10)

`B_coverage_all_sides_all_wordings` ist bereits gruen.
