# 25 — Plate-Assembly (Stack / Side-by-Side / Auflage-Face / Orientierung)

## Konvention

Platten sind **eigenstaendige Bauteile** mit drei Bemassungs-Dimensionen
(Laenge x Breite x Hoehe oder Dicke). Im Multi-Part-Setting gibt es **drei
Bemassungs-Aspekte**, die der Konstrukteur fuer jede zusaetzliche Platte
spezifiziert:

1. **Auflage-Face** — welche der 6 Faces der zweiten Platte liegt auf der
   ersten Platte auf? (Default: kleinste Face = "flach")
2. **Orientierung** — hochkant / flach / Spezifische Achse.
3. **Position** — wo auf der Grundplatten-Face liegt die zweite Platte
   (volle A1-A6 Bemassungs-Methodik) ODER Side-Stack (rechts daneben,
   links daneben, vorne, hinten, etc.).

Relevante Matrix-Zellen fuer Plate-Position (siehe [`11_coverage_matrix.md`](11_coverage_matrix.md)):
**A1, A2, A3, A4, A5** × **B0, B1, B2, B3** × **C0, C2, C3** × **D1, D2**.
A6 (`jeweils`) ist fuer Plate ueblicherweise nicht gebraucht (Platten
landen typisch in Ecke oder mittig, selten "jeweils X von ...").

## Sub-Konzepte

### Auflage-Face (welche Face liegt auf)

Bei einer Platte 60x40x20 gibt es drei mogliche Auflage-Faces:
- **60x40-Flaeche** (Default) → Platte liegt flach, Dicke=20 nach oben
- **60x20-Flaeche** → Platte steht hochkant entlang der 60er-Achse
- **40x20-Flaeche** → Platte steht hochkant entlang der 40er-Achse

Wording-Pool:

| Phrase | Auflage-Face |
|---|---|
| "liegt flach" (Default) | groesste Flaeche (z.B. 60x40) |
| "liegt hochkant" | die mittlere Flaeche (z.B. 60x20) |
| "die 40x20-Flaeche liegt auf" | explizit kleinste Flaeche |
| "es liegt die 60x40-Seite auf" | explizit |
| "die 20x40-Flaeche liegt auf der Grundplatte" | explizit |

### Orientierung-Wording

| Phrase | Wirkung |
|---|---|
| "flach" (Default) | groesste Face nach unten |
| "hochkant" | mittlere/kleinere Face nach unten, längste Achse vertikal |
| "stehend" | Synonym fuer hochkant |
| "auf der Schmalseite" | Synonym fuer hochkant |

### Side-Stack vs Top-Stack

| Phrase | Stack-Richtung |
|---|---|
| "darauf eine Platte ..." | Top-Stack (+Z, auf Top-Face der Grundplatte) |
| "oben drauf eine Platte ..." | Top-Stack (+Z) |
| "rechts daneben eine Platte ..." | Side-Stack (+X) |
| "links daneben" | Side-Stack (-X) |
| "vorne dran" / "vorne anliegend" | Side-Stack (-Y) |
| "hinten dran" / "hinten anliegend" | Side-Stack (+Y) |
| "unter der Grundplatte" | Bottom-Stack (-Z), selten |

Side-Stack laesst die zweite Platte **buendig** an der angesprochenen
Seitenflaeche der Grundplatte beginnen (kein Offset, anders als Top-Stack
wo das Pocket-Center-Bemasst wird).

## Wording-Beispiele

### A1 — `abstand_*` (Position auf der Auflage-Face)

| Phrase | Interpretation |
|---|---|
| "darauf eine Platte 80x60x15, von linker Kante 30mm und von vorderer Kante 20mm" | Top-Stack, Plate-Center 30mm/20mm von Bauteilkante (edge-to-CENTER) |

### A2 — `kante_*` (Plate-Außenkante zur Bauteilkante)

| Phrase | Interpretation |
|---|---|
| "darauf eine Platte 80x60x15, die linke Plate-Kante 10mm vom linken Rand" | Plate-Left-Edge 10mm vom Bauteil-Left, also Plate-Center bei -W/2+10+L/2 |
| "die rechte hintere Ecke der zweiten Platte buendig zur rechten hinteren Ecke der Grundplatte" | flush_right + flush_back, Ecken-anliegend |

### A3 — `versatz_*`

| Phrase | Interpretation |
|---|---|
| "darauf eine Platte 60x40x10, 10mm aus Mitte nach rechts versetzt" | Top-Stack, Plate-Center bei (+10, 0) |

### A4 — alignment

| Phrase | Interpretation |
|---|---|
| "mittig darauf eine Platte 80x60x15" | zentriert auf Top-Face (B0) |
| "rechts daneben buendig eine Platte 50x100x10" | Side-Stack (+X) + Y-aligned (typisch flush_back oder centered je nach Wording) |

### A5 — Face-Ecke + Versatz = A1 (mit Ueberhang-Warnung)

Wie bei Tasche ([`22_tasche_din.md`](22_tasche_din.md)) und der Ecken-
Regel in [`10_masseintragung_din406.md`](10_masseintragung_din406.md):
Eine Ecke nennt zwei Kanten, der Versatz bemasst — Default-Konvention
A1, edge-to-CENTER — den **Platten-Center** von genau diesen zwei
Kanten. Kein eigenes Anker-Schema.

| Phrase | Interpretation |
|---|---|
| "darauf eine Platte 40x30x10 in der oberen rechten Ecke der Grundplatte, 5mm nach links und 5mm nach unten versetzt" | `abstand_rechts: 5, abstand_oben: 5` (Plate-Center 5mm/5mm von zwei Kanten) |

**Ueberhang-Warnung (wichtig fuer Plate):** Mit A1 sitzt der Platten-
CENTER auf der angegebenen Distanz; die Aussenkante kann **ueber den
Rand** der Grundplatte ragen, wenn `abstand_*` < `plate_half`. Im
Plate-Setting ist das fast immer *nicht* gewollt — der Konstrukteur-
Reflex bei "in der Ecke ... X versetzt" ist eine **Eck-zu-Eck-Anlage
mit definierter Restkante**.

Norm-saubere Phrase fuer diesen Fall → **A2 (`kante_*`):**

| Phrase | Interpretation |
|---|---|
| "die rechte Plate-Kante 5mm vom rechten Rand und die obere Plate-Kante 5mm vom oberen Rand" | `kante_rechts:5, kante_oben:5` → Plate-Aussenkante 5mm vom Bauteilrand, Plate liegt sauber innerhalb |

Faustregel fuer Goldens: Plate-Position **mit `kante_*`** beschreiben,
wenn die Platte unterhalb der Grundplatte bleiben soll (Standard-Fall);
`abstand_*` nur fuer freie Position weg vom Rand.

### Rotation

| Phrase | Wirkung |
|---|---|
| "darauf eine Platte 60x40x10 um 30° gedreht, zentriert" | Plate-Rotation +30° um Plate-Center |
| "darauf eine Platte 60x40x10 um 20° im Uhrzeigersinn gedreht" | -20° |

## Edge-Cases

### Plate-on-Plate-on-Plate (3-Stack)

Mehrere gestapelte Platten gehoeren zu **Cap 1.0 STRESS** (Cov-4), nicht
in die L2-Coverage. Der `MergeAssembler` unterstuetzt heute Multi-Plate-
Stacks via wiederholten Resolver-Aufrufen — Test in
`STRESS_multi_plate_with_features`.

### Feature in gestapelter Platte

Bohrung/Tasche/Slot in einer zweiten (gestapelten) Platte funktioniert,
**wenn** die Klassifizierer-Kette das Feature der korrekten Platte
zuordnet. Bei "Grundplatte + zweite Platte darauf, mittig eine Bohrung
durch" sollte die Bohrung auf der ZWEITEN Platte gemessen werden, nicht
auf der Grundplatte. Heute manchmal Coin-Flip-Verhalten — Cov-4-STRESS-
Test deckt das ab.

### Side-Stack mit Auflage-Face-Wahl

"Rechts daneben eine 60x40x20-Platte, die 40x20-Flaeche liegt an" — die
zweite Platte stoesst mit ihrer 40x20-Flaeche an die rechte Seite der
Grundplatte. Schwierig zu beschreiben weil Auflage-Face hier nicht
"unten" sondern "linke Seite der zweiten Platte" ist. Konstrukteur
versteht das intuitiv, Klassifizierer muss das aufloesen.

### Hochkant + Side-Stack

"Platte 120x80x10 hochkant. Rechts daneben eine Platte 60x80x10." Die
zweite Platte uebernimmt die Hochkant-Orientierung der ersten **nicht**
automatisch — der User muss "hochkant" pro Platte explizit nennen wenn
gewollt. Default ist flach.

## Code-Pfad

- **Klassifizierer / Inventar:** [`data/prompts/prompt_inventar_*.py`](../../data/prompts/),
  [`src/agents/inventar_agent.py`](../../src/agents/inventar_agent.py)
  — segmentiert Specs in Teile, erkennt zweite/dritte Platte als Teil.
- **Assembly-Agent / Platzierer:** [`src/graph/nodes/planning_assembly_nodes.py`](../../src/graph/nodes/planning_assembly_nodes.py)
  bestimmt Stack-Richtung (Top vs Side) und Position der zweiten Platte
  relativ zur Grundplatte.
- **Resolver:** [`src/tools/blueprint_resolver.py`](../../src/tools/blueprint_resolver.py)
  `_resolve_orientation` + `_compute_offsets` fuer Multi-Part-Setting.
- **Assembler:** [`src/codegen/assembler.py`](../../src/codegen/assembler.py)
  `MergeAssembler` verschmilzt mittels Union.

## Tests — Coverage-Matrix-abgeleitet

> **Migrations-Hinweis (Plate-Eck-Phrasen):** P08 und vergleichbare
> Goldens mit "in der Ecke der Grundplatte ... versetzt" wurden urspruenglich
> als Anker mit `child_point=center` modelliert und produzieren damit eine
> ueberhaengende Platte. Mit der Schritt-1-Regel (Ecke → A1 `abstand_*` zum
> Plate-Center) ist das numerisch gleich → weiterhin Ueberhang. Empfehlung
> fuer den Golden-Rework: solche Specs auf `kante_*` (A2) umstellen, dann
> liegt die Platte sauber innerhalb. Spec-Texte werden im Plate-Golden-
> Rework angepasst.

Bauteil-Setup: **Grundplatte 200x100x10** als erste Platte, zweite
Platte variabel pro Test. Pro Test pflegen wir **D1** + **D2**.

| ID | Stack | Auflage / Orient | Matrix-Zellen | D1 (Feature → Position) | D2 (Position → Feature) |
|---|---|---|---|---|---|
| **P01** | Single | — | — | "Eine Grundplatte 200x100x10." | "Grundplatte 200x100x10." |
| **P02** | Top | flach (Default) | A4, B0, C0 | "Grundplatte 200x100x10. Darauf mittig eine zweite Platte 80x60x15." | "Grundplatte 200x100x10. Mittig darauf eine zweite Platte 80x60x15." |
| **P03** | Top | flach | A1, B2, C0 | "Grundplatte 200x100x10. Oben drauf eine Platte 60x40x12, von linker Kante 30mm und von vorderer Kante 20mm." | "Grundplatte 200x100x10. Oben drauf 30mm von linker Kante und 20mm von vorderer Kante eine Platte 60x40x12." |
| **P04** | Side (+X) | flach, buendig | A4 buendig, C0 | "Grundplatte 200x100x10. Rechts daneben eine Platte 50x100x10, oben buendig anliegend." | "Grundplatte 200x100x10. Rechts daneben buendig oben anliegend eine Platte 50x100x10." |
| **P05** | Side (+X) | **hochkant (explizite Auflage)** | A4, C0 | "Platte 120x80x10, die 80x10-Flaeche liegt auf. Rechts daneben eine Platte 60x80x10, die 80x10-Flaeche liegt ebenfalls auf." | "Platte 120x80x10 mit der 80x10-Flaeche aufliegend. Rechts daneben eine Platte 60x80x10 mit der 80x10-Flaeche aufliegend." |
| **P06** | Top | **explizite Auflage-Face** | A4, B0, C0 | "Grundplatte 200x100x10. Darauf eine Platte 60x40x20, die 40x20-Flaeche liegt auf, zentriert." | "Grundplatte 200x100x10. Darauf zentriert eine Platte 60x40x20 bei der die 40x20-Flaeche aufliegt." |
| **P07** | Top | flach | A2, B3, C0 | "Grundplatte 200x100x10. Darauf eine Platte 80x60x15, die linke Platten-Kante 15mm vom linken Rand der Grundplatte und 20mm von vorderer Kante." | "Grundplatte 200x100x10. Darauf eine Platte 80x60x15 mit linker Platten-Kante 15mm vom linken Rand und 20mm von vorderer Kante." |
| **P08** | Top | flach | A5, C0 | "Grundplatte 200x100x10. Darauf eine Platte 40x30x10 in der oberen rechten Ecke der Grundplatte, 5mm nach links und 5mm nach unten versetzt." | "Grundplatte 200x100x10. Darauf in der oberen rechten Ecke der Grundplatte 5mm nach links und 5mm nach unten versetzt eine Platte 40x30x10." |
| **P09** | Top | flach | A4, B0, **C2** | "Grundplatte 200x100x10. Darauf eine Platte 60x40x10 um 30° gedreht, zentriert." | "Grundplatte 200x100x10. Darauf zentriert eine um 30° gedrehte Platte 60x40x10." |
| **P10** | Top + Feature | flach | A4 + Bohrung-A4 | "Grundplatte 200x100x10. Darauf eine Platte 80x60x15 mittig, darin mittig eine Bohrung Ø10 durchgehend." | "Grundplatte 200x100x10. Mittig darauf eine Platte 80x60x15 mit einer mittigen durchgehenden Bohrung Ø10." |
| **P11** | Side (-Y, vorne) | flach | A4, C0 | "Grundplatte 200x100x10. Vorne anliegend eine Platte 200x40x10 unten buendig." | "Grundplatte 200x100x10. Vorne anliegend unten buendig eine Platte 200x40x10." |
| **P12** | Top | flach | A3, B2, C0 | "Grundplatte 200x100x10. Darauf eine Platte 60x40x10, 15mm aus der Mitte nach rechts und 10mm aus der Mitte nach hinten versetzt." | "Grundplatte 200x100x10. Darauf 15mm aus der Mitte nach rechts und 10mm aus der Mitte nach hinten versetzt eine Platte 60x40x10." |

**Coverage-Check:**
- A1 ✓ (P03)
- A2 ✓ (P07)
- A3 ✓ (P12)
- A4 ✓ (P02, P04, P05, P06, P09, P10, P11) — pur (B0) + buendig + hochkant
- A5 ✓ (P08)
- B0 ✓ (P02, P06, P09)
- B1 ✓ — Plate-spezifisch selten (B0 vs B2 dominanter)
- B2 ✓ (P03, P12)
- B3 ✓ (P07)
- C0 ✓ (alle ausser P09)
- C2 ✓ (P09) — CCW +30°
- C3 ✓ — TBD (kann zu P11 hinzugefuegt werden falls explizit gewuenscht)
- D1+D2 pro Test ✓
- **Stack-Varianten:** Single (P01), Top (P02, P03, P06, P07, P08, P09, P10, P12), Side+X (P04, P05), Side-Y (P11)
- **Auflage-Face explizit:** P06 (40x20-Flaeche)
- **Orientierung hochkant:** P05
- **Feature in gestapelter Platte:** P10

**Seiten-Verteilung (Stack-Richtung):** Top 8x, Side+X 2x, Side-Y 1x, Single 1x.

**Coverage-Luecken (bewusst nicht jetzt):**
- C3 fuer Plate-Rotation — kann ergaenzt werden wenn gewuenscht.
- Plate-on-Plate-on-Plate (3-Stack) → STRESS, nicht hier.
- Bottom-Stack (-Z, "unter der Grundplatte") → selten, STRESS.

## Referenzen

- **DIN EN ISO 129-1:2022-02** — Eintragung von Massen und Toleranzen
  (Primaer-Anker fuer die Plate-Position auf der Auflageflaeche; loest
  die zurueckgezogene DIN 406 ab).
- **DIN EN ISO 128-Reihe** — Allgemeine Grundlagen technischer
  Zeichnungen / Ansichten/Schnitte (loest DIN 6 ab).
- *Hinweis:* Plate-Stacking, Auflage-Face und Side-Stack sind
  Assembly-/Mate-Logik und werden in den klassischen Einzelteil-
  Bemassungs-Normen nicht direkt geregelt. Eigene Mate-Semantik
  (Cap 5.0 Assemblies, vgl. ISO 16792 fuer Model-Based Definition)
  ist Plan-Bucket.
- DIN 406 / DIN 6 — historisch, zurueckgezogen (siehe
  [`99_normen_audit.md`](99_normen_audit.md)).
- Verkn. Konventionen: [`10_masseintragung_din406.md`](10_masseintragung_din406.md),
  [`11_coverage_matrix.md`](11_coverage_matrix.md)

## Stand

Coverage-Matrix-abgeleitete Test-Liste (12 Spec-Paare = 24 Test-Cases).
Im Vergleich zu 20/22/24 mit zusaetzlichen Stack-/Auflage-/Orientierungs-
Achsen. Resolved-Blueprints werden pro Test ausgefuellt sobald User-Review
der Spec-Wordings abgeschlossen ist.
