# 10 — Masseintragung (DIN 406, ISO 129)

## Konvention

Drei grundlegende Bemassungs-Arten unterscheiden sich an der **Bezugs-
Stelle** des Masses:

| Schema-Feld | Konvention | Konstrukteur-Wording |
|---|---|---|
| `edge_distances` (heute oft `abstand_*`) | Bauteil-Edge zum **Feature-CENTER** | "von linker Kante 12mm", "von oben 20mm entfernt" |
| `pocket_edge_distances` (heute oft `kante_*`) | Bauteil-Edge zur **Feature-EDGE** | "deren linke Kante 12mm von linker Wuerfelkante", "die rechte Kante der Tasche von rechter Wuerfelkante 25mm" |
| `center_offset` (heute oft `versatz_*`) | Aus dem Bauteil-CENTER um N mm in eine Richtung | "10mm nach rechts versetzt", "5mm aus Mitte nach unten" |

Default bei Mehrdeutigkeit: **edge-to-CENTER** fuer Bohrungen (point-like)
und Pockets (Konstrukteur sagt typisch "Tasche 20mm von rechts" = Pocket-
Center 20mm vom Rand). Edge-to-EDGE explizit nur wenn die Phrase die
**Feature-Kante** nennt ("deren X-Kante", "die X-Kante der Tasche").

**Slots/Nuten haben eine eigene Sub-Konvention** weil sie zwei verschieden
zu behandelnde Achsen haben (Length vs Width). Siehe
[`21_nut_slot_din.md`](21_nut_slot_din.md).

## Wording-Beispiele

### `abstand_*` (edge-to-CENTER)

| Phrase | Interpretation |
|---|---|
| "Bohrung 8mm von linker Kante 12mm und von oberer Kante 18mm entfernt" | Bohrungs-Center bei (-W/2 + 12, +H/2 - 18) |
| "Tasche 60x40 von oben 20mm und von links 30mm entfernt" | Pocket-Center 20mm und 30mm von den Bauteilkanten |
| "Bohrung jeweils 12mm von den Kanten entfernt" | abstand_unten=12 + abstand_rechts=12 (jeweils) |

### `kante_*` (edge-to-EDGE)

| Phrase | Interpretation |
|---|---|
| "Tasche deren rechte Kante 25mm von rechter Wuerfelkante" | Pocket-Right-Edge bei +W/2 - 25, Pocket-Center bei (+W/2 - 25 - L/2) |
| "Pocket deren obere Kante 15mm und linke Kante 20mm von Wuerfelkante entfernt" | Pocket-Top-Edge und Pocket-Left-Edge auf Distanz |
| "Nut die untere Kante von unten 12mm entfernt" | Slot-Bottom-Edge bei -H/2 + 12 (siehe Slot-Konvention) |

### `versatz_*` (center-relativ)

| Phrase | Interpretation |
|---|---|
| "10mm nach rechts versetzt" | aus Bauteil-Center um +10 in X verschoben |
| "5mm aus Mitte nach unten" | aus Bauteil-Center um -5 in Y verschoben |
| "obere rechte Ecke 10mm nach unten und 20mm nach links versetzt" | Anchor (top_right) + offset (down:10, left:20) — siehe Anchor-Konvention |

## Edge-Cases

### "von der Kante" vs "die Kante" — Distinktion

Die Praeposition entscheidet:

- **"von der X-Kante"** / **"X mm von X-Kante"** → `abstand_*`
  (Center-Bezug; das Mass kommt **von** der Bauteilkante zur Feature-
  Mitte hin).
- **"die X-Kante der Tasche/Nut/..."** / **"deren X-Kante"** → `kante_*`
  (Feature-Edge-Bezug; das Mass spricht von der **Feature**-Kante).

Wenn die Phrase BEIDE Kanten nennt ("die obere Kante der Tasche von
der oberen Wuerfelkante"), gewinnt explizit `kante_*`.

### Mehrere Achsen mit verschiedenen Konventionen

Pro Achse gilt unabhaengig die zur Phrase passende Konvention. Beispiel:
"deren rechte Kante 25mm von rechter Wuerfelkante und 5mm aus Mitte
nach oben" → X-Achse `kante_rechts`, Y-Achse `versatz_oben`.

Resolver kombiniert per-Achse via Prioritaets-Reihenfolge:
1. `anchor` (Punkt-zu-Punkt)
2. `pocket_edge_distances` (edge-to-EDGE)
3. `edge_distances` (edge-to-CENTER)
4. `center_offset` (additiv auf der Edge-Basis ODER eigenstaendig wenn keine Edge auf der Achse)
5. `alignment` (centered / flush_*)

### "jeweils" Mehrdeutigkeit

"jeweils 10mm von den Kanten" bedeutet: 10mm zu beiden relevanten Kanten
der Position. "unten rechts jeweils 10mm" → abstand_unten=10 +
abstand_rechts=10. Klassifizierer-Prompt enthaelt diese Regel.

## Code-Pfad

- **Klassifizierer-Prompts:** [`data/prompts/prompt_classifier_pocket.py`](../../data/prompts/prompt_classifier_pocket.py),
  [`prompt_classifier_slot.py`](../../data/prompts/prompt_classifier_slot.py),
  [`prompt_classifier_hole.py`](../../data/prompts/prompt_classifier_hole.py).
  Definieren wann der LLM `abstand_*` vs `kante_*` vs `versatz_*` emittiert.
- **Feature-Builder:** [`src/tools/feature_builder.py`](../../src/tools/feature_builder.py)
  `_extract_edge_distances` / `_extract_pocket_edge_distances` /
  `_extract_center_offset`. Mappt Klassifizierer-Output auf Schema-Felder.
- **Resolver:** [`src/tools/blueprint_resolver.py`](../../src/tools/blueprint_resolver.py)
  `_compute_offsets` und `_apply_edge_distances_axis`. Wendet die
  geometrische Konvention an.

## Tests

- Unit: [`tests/tools/test_kante_vs_abstand.py`](../../tests/tools/test_kante_vs_abstand.py) — 16 Cases die
  alle drei Konventionen plus Mischformen abdecken.
- Component-Goldens: [`tests/golden/components/T_kombo_basics/`](../../tests/golden/components/T_kombo_basics/) (Pocket, 14
  Variationen), [`B_kombo_*/`](../../tests/golden/components/) (Bohrung), [`N_kombo_basics/`](../../tests/golden/components/N_kombo_basics/) (Slot).
- DSPy-Demos: [`data/dspy_training/klassifizierer_traces.py`](../../data/dspy_training/klassifizierer_traces.py)
  enthaelt explizite Pocket/Slot/Hole-Demos pro Konvention plus
  Grenzfall-Demos (Section "Grenzfall: 'deren X-kante' vs 'von X-kante'").

## Referenzen

- DIN 406 — Technische Zeichnungen, Maßeintragung
- ISO 129-1 — Technische Produktdokumentation, Eintragung von
  Massen und Toleranzen
- DIN 6 — Darstellung in Schnitten (kontextuell relevant)

## Stand

Aktiv seit Capability 1.0 (heutige Pocket/Bohrung-Logik). Slot-Sub-
Konvention seit 2026-05-14 (ADR 0008-Foundation, Resolver per-Achse-Logik).
