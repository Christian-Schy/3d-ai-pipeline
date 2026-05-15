# B_coverage_all_sides_all_wordings — Bohrung L2-Coverage-Golden

**Capability 1.0 — Bohrung. Cov-3-Stufe ([CLAUDE.md](../../../../CLAUDE.md)
"L2-Coverage-Goldens").**

Eine Capability komplett: alle 6 Seiten + alle DIN-Wording-Varianten
A1/A3/A4/A5/A6 × B0-B3 × C0 auf einem **Wuerfel 100x80x40**.

## Test-Faelle (aus [`docs/conventions/20_bohrung_din.md`](../../../../docs/conventions/20_bohrung_din.md))

10 Bohrungen H01-H10. Jeder Fall ist eine isolierte Konventions-Variante:

| Feature | Face | Matrix-Zellen | DIN-Bezug |
|---|---|---|---|
| `h01_oben_a1_b2` | oben | A1, B2 | edge-to-CENTER, beide Achsen |
| `h02_vorne_a3_b2` | vorne | A3, B2 | center-offset, beide Achsen |
| `h03_unten_a1_a3_b3` | unten | A1+A3, B3 | edge-distance + center-offset |
| `h04_hinten_a4_a1_b1` | hinten | A4+A1, B1 | alignment + single-axis edge-distance |
| `h05_links_a4_pur` | links | A4 (pur) | reines zentriert |
| `h06_rechts_a6` | rechts | A6 | "jeweils X von zwei Kanten" |
| `h08_unten_a1_a4_b1` | unten | A1+A4, B1 | single-axis edge-distance |
| `h09_hinten_a3_a4_b1` | hinten | A3+A4, B1 | single-axis center-offset |
| `h10_oben_a4_a3_b3` | oben | A4+A3, B3 | center-offset auf einer Achse |

**Hinweis A5**: A5 (Bauteil-Face-Ecke + Versatz) entfaellt fuer Bohrung —
Bohrungen sind point-like und haben keine eigene Ecke. Phrasen wie "in
der oberen rechten Ecke, 8mm nach links versetzt" sind mathematisch
identisch zu A1 mit `abstand_rechts: 8`. Konvention 20_bohrung_din.md
A5-Sektion dokumentiert das. A5 gilt fuer Plate/Tasche/Pattern.

**Coverage-Check:**
- A1 ✓ (H01, H03, H04, H06, H08) — beide Achsen + single-Achse
- A3 ✓ (H02, H03, H09, H10)
- A4 ✓ (H04, H05, H08, H09, H10) — pur + single-axis
- A6 ✓ (H06)
- B0 ✓ (H05) — Pur-zentriert
- B1 ✓ (H04, H08, H09) — single-axis
- B2 ✓ (H01, H02) — beide Achsen edge/offset
- B3 ✓ (H03, H10) — Mischform
- C0 ✓ (alle) — keine Rotation
- **Alle 6 Seiten:** oben (H01, H10), unten (H03, H08), vorne (H02),
  hinten (H04, H09), links (H05), rechts (H06).

## Resolver-Mathe

Wuerfel 100x80x40 → Face-Half:
- `>Z` / `<Z` (oben/unten): face_w=100, face_h=80 → Half (50, 40)
- `>Y` / `<Y` (hinten/vorne): face_w=100, face_h=40 → Half (50, 20)
- `>X` / `<X` (rechts/links): face_w=80, face_h=40 → Half (40, 20)

Beispiel H01 (oben, A1 edge-to-CENTER):
- edge_distances `{left: 25, vorne: 20}` auf `>Z`
- `left → wx-1`: ox = -1*(50 - 25) = **-25**
- `vorne → wy-1`: oy = -1*(40 - 20) = **-20**

## Pipeline-Test

`pipeline/specs.txt` enthaelt eine D1-Variante (Feature-zuerst). D2-Varianten
und weitere Wording-Permutationen kommen zur naechsten Iteration.

## Was dieser Test absichert

- Klassifizierer-Pfad fuer Bohrung auf allen 6 Seiten
- Klassifizierer-Erkennung von "jeweils"-Pattern (A6)
- Normalizer-Schritte (frame/alignment/anchor/offset)
- Resolver-Math fuer alle Edge-Distance-/Center-Offset-Pfade
- Multi-Feature-Aggregation auf einem Bauteil

## Naechste L2-Goldens (Plan)

- `T_coverage_all_sides_all_wordings` (Pockets/Taschen, T01-T12)
- `N_coverage_all_sides_all_orientations` (Slots/Nuten, N01-N12)
- `M_coverage_patterns_all_kinds` (Grid/Kreis/Linear, M01-M10)

Nach allen 4 L2-Goldens gruen + Done-Review-Checkliste (ADR 0008):
Capability 1.0 → Cov 3 vollstaendig. Danach Cov 4 (L3-STRESS-Goldens).
