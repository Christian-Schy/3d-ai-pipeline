# 10 — Masseintragung (ISO 129-1)

> Norm-Anker: **DIN EN ISO 129-1:2022-02**. Die fruehere DIN 406 ist
> zurueckgezogen — siehe [`99_normen_audit.md`](99_normen_audit.md).
> Dateiname `_din406` bleibt vorerst (Link-Stabilitaet), wird im
> Doku-Sweep mit umbenannt.

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
| "Bohrung obere rechte Ecke, 10mm von oben und 20mm von rechts" | Ecken-Regel: abstand_oben=10 + abstand_rechts=20 (Ecke = zwei Kantenmasse) |

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

### Ecken-Phrase → Ecken-Regel (zwei `abstand_*`)

"Obere rechte Ecke" o.ae. ist **kein eigener Bezugstyp** — eine Ecke ist
nur der Punkt, an dem zwei Bauteilkanten zusammentreffen. Eine Eck-
Platzierung zerfaellt in **zwei `abstand_*`-Kantenmasse** (Ecken-Regel):

| Phrase | Interpretation |
|---|---|
| "obere rechte Ecke, 10mm nach unten und 20mm nach links versetzt" | `abstand_oben: 10` + `abstand_rechts: 20` |

Das Wort "versetzt"/"versatz" macht daraus **kein** `versatz_*` (A3) — der
Bezug ist die Kante/Ecke, nicht die Bauteilmitte. Der Resolver wendet
danach die feature-typische Mathematik an (Bohrung edge-to-center, Nut
per-Achse). Es entsteht **kein** `anchor`. Details:
[`ecken_regel.md`](../../data/prompts/conventions/ecken_regel.md).

Der `anchor` bleibt ausschliesslich dem expliziten "auf"-Bezug
vorbehalten ("liegt auf der rechten Kante an") — eine echte Punkt-auf-
Punkt-Beziehung, kein Eck-Versatz.

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

### Mass-Ketten (DIN-Anti-Pattern)

ISO 129-1 raet (wie zuvor DIN 406) **explizit ab von Mass-Ketten** ("von
links 10, dann 20, dann 15") weil sie Toleranzen aufsummieren.
Konstrukteure setzen stattdessen alle Masse von einem **gemeinsamen
Bezug** aus.

Im Pipeline-Kontext heisst das: wenn der User "von linker Kante 10mm, dann
weitere 20mm zur naechsten Bohrung" sagt, **muss** der Normalizer/
Klassifizierer das in absolute Masse aufloesen:

| User-Phrase | Aufloesung |
|---|---|
| "Bohrung A 10mm von links, Bohrung B 20mm weiter rechts" | A: `abstand_links: 10`, B: `abstand_links: 30` |
| "von oben 5, dann 15 weiter, dann 10 weiter (3 Bohrungen)" | `abstand_oben: 5`, `abstand_oben: 20`, `abstand_oben: 30` |

Der Klassifizierer erkennt Trigger-Woerter ("dann", "weiter", "danach",
"jeweils zusaetzliche") und akkumuliert die Distanz auf den letzten
gemeinsamen Bezug. Wenn kein gemeinsamer Bezug erkennbar ist (z.B. "10mm
zwischen den Bohrungen"), ist das ein **Feature-zu-Feature-Bezug**
(Capability 6.0 / Coverage-Matrix A7), nicht A1.

Heute (Cap 1.0) ist Mass-Ketten-Aufloesung **noch nicht implementiert** —
Klassifizierer-Prompt sollte zumindest mit "ungekettete" Mass-Eingabe
korrekt umgehen und kettenartige Phrasen als Limitation kennen.

**Anti-Empfehlung an den User:** wenn moeglich, beim Beschreiben pro
Feature direkt den absoluten Abstand zur Bauteilkante nennen, nicht
inkrementell.

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

- **DIN EN ISO 129-1:2022-02** — Technische Produktdokumentation (TPD),
  Eintragung von Massen und Toleranzen — Teil 1: Allgemeine Grundlagen.
  Primaer-Anker; loest die zurueckgezogene DIN 406 ab.
- **DIN EN ISO 128-Reihe** — Darstellung in Ansichten/Schnitten; loest
  die zurueckgezogene DIN 6 ab.
- DIN 406 / DIN 6 — historisch, zurueckgezogen. Nur als Kontext, nicht
  als aktiver Anker (siehe [`99_normen_audit.md`](99_normen_audit.md)).

## Stand

Aktiv seit Capability 1.0 (heutige Pocket/Bohrung-Logik). Slot-Sub-
Konvention seit 2026-05-14 (ADR 0008-Foundation, Resolver per-Achse-Logik).
