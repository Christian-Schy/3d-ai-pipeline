# 90 — User-Wording-Beispiele pro Capability

Sammlung von Konstrukteur-Phrasen, die die Pipeline pro Capability
verstehen muss. Wird von den DSPy-Demo-Pools, agent_regression-Suiten
und Goldens gespeist.

Dies ist eine **Referenz fuer Reviewer** und neue Mitarbeiter — keine
SOLL-Phrasen-Liste. Wenn eine Phrase hier steht und nicht funktioniert,
ist das ein Bug oder eine fehlende Demo. Wenn eine Phrase NICHT hier
steht, ist sie potentielles Erweiterungs-Material fuer den Demo-Pool.

Single Source of Truth fuer die geometrische Bedeutung: die jeweiligen
`<XX>_<capability>_din.md`-Docs.

---

## Cap 1.0 — Primitive Assembly

### Bohrungen ([20_bohrung_din.md](20_bohrung_din.md))

**A1 — Abstand zur Bauteilkante (point-like, edge-to-center):**
- `oben eine 8mm bohrung 12 tief von linker kante 25mm und von vorderer kante 30mm`
- `vorne eine bohrung durchmesser 6 10 tief 20mm von oben und 15mm von rechts`
- Voice-Style: `oben bohrung 8 durchmesser 12 tief von links 30 von vorne 20`

**A3 — Versatz aus Mitte:**
- `oben eine 10mm bohrung 8 tief 12mm aus der mitte nach hinten versetzt`
- `oben eine bohrung 8mm 10 tief von der mitte 20mm nach rechts und 10mm nach vorne versetzt`

**A5 — Ecke + Versatz (= A1 Ecken-Regel):**
- `oben eine 8mm bohrung 10 tief in der oberen rechten ecke 22mm nach links und 18mm nach unten versetzt`
- `oben eine bohrung 6mm 8 tief in der unteren linken ecke 15mm nach rechts und 12mm nach oben versetzt`
- NEST-Variante (Bohrung in Tasche): `obere rechte ecke 3mm nach unten 5mm nach links versetzt eine 4mm bohrung 3 tief`

**Anker (Punkt-zu-Punkt):**
- `obere rechte ecke der bohrung an der oberen rechten ecke der platte`
- `bohrungsmittelpunkt 10mm unter der oberen rechten plattenecke`

**Zentriert (keine Positionsangabe):**
- `hinten eine zentrierte bohrung 12mm durchgehend`
- `oben mittig eine 10mm bohrung 15 tief`

### Pockets / Taschen ([22_tasche_din.md](22_tasche_din.md))

**A1 — Pocket-Center via Abstand:**
- `unten eine tasche 30x20x6 mit kantenabstand top 12 und right 18`

**A2 — Pocket-Edge via Abstand (`kante_*`):**
- `auf der platte oben eine tasche 30x20x5 deren rechte kante 5mm und untere kante 3mm von der plattenkante entfernt`

**A3 — Versatz aus Mitte mit Rotation:**
- `oben eine tasche 28x18x5 12mm aus der mitte nach rechts versetzt um 30 grad gedreht`

**A5 — Ecke + Versatz:**
- `unten eine tasche 25x18x6 in der oberen rechten ecke 22mm nach links und 18mm nach unten versetzt`

### Slots / Nuten ([21_nut_slot_din.md](21_nut_slot_din.md))

**Endpunkt-basiert:**
- `oben eine nut entlang der x-achse anfangspunkt 20mm von linker kante endpunkt 80mm von linker kante breite 5 tiefe 4`

**Mittellinien-Bezug (DIN-Konvention, beide Achsen edge-to-center):**
- `oben eine nut 30mm lang 5mm breit 4 tief 15mm von hinterer kante entfernt`
- `rechts eine nut entlang der y-achse mit länge 30 breite 5 tiefe 4`

**Diagonal:**
- `oben eine nut länge 30 breite 4 tiefe 3 um 45 grad gedreht 25mm aus mitte nach links und 25mm nach unten versetzt`

### Patterns ([24_pattern_din.md](24_pattern_din.md))

**Lochkreis (circular):**
- `oben lochkreis 60mm mit 6 bohrungen 10mm durchmesser durchgaengig`
- `oben ein lochkreis aus 6 bohrungen 8mm durchmesser 5 tief auf einem teilkreis von 60mm`
- `oben 8x lochkreis 50mm Ø6 mit 4 tiefe`
- Mit Startwinkel: `oben lochkreis 60mm mit 6 bohrungen 8mm 5 tief erste bohrung bei 90 grad`
- Synonym: `rechts ein lochkreis 50mm mit 4 bohrungen 6mm durchmesser erste bohrung oben` (= 90°)

**Raster (grid):**
- `rechts ein 2x2 lochmuster mit 6mm bohrungen 4 tief randabstand 8mm zur kante`
- `oben ein 3x2 raster aus 5mm bohrungen mit 20mm rasterabstand`
- Eckbohrungen (4 Loecher mit gleichem Randabstand): `oben eckbohrungen mit 8mm bohrungen 5 tief 10mm randabstand`

**Linear-Reihe:**
- `vorne eine bohrungsreihe aus 4 bohrungen 5mm durchmesser 4 tief mit 15mm abstand entlang der z-achse`

### Multi-Part (Platte auf Wuerfel)

- `100mm wuerfel, oben drauf eine platte 60x40x10 mittig`
- `100mm wuerfel, rechts eine platte 40x40x10 hochkant flush mit oberkante`
- `100mm wuerfel, oben links in der ecke eine 50x50x10 platte buendig anliegend`

### Voice-Style / Run-on

- `mach mir einen würfel 100x100x80, oben mittig eine 10mm bohrung 15 tief, oben rechts in der ecke 15mm nach links und 10mm nach unten versetzt eine 6mm bohrung 8 tief, unten zentral ein lochkreis 50mm mit 6 bohrungen 5mm durchmesser 4 tief mit startwinkel 90, ...`
- (siehe `tests/golden/components/STRESS_voice_long/splitter/spec.txt` fuer 15-Aktionen-Beispiel)

---

## Cap 2.0+ (zukuenftig)

Bei Aufnahme einer Capability hier ergaenzen. Die Eintraege fuer
Cap 2.0 (Modifications mit Fasen/Rundungen-Kanten-Auswahl), Cap 4.0
(Connections: Senkungen/Gewinde), Cap 6.0 (Constraint-Bemassung) etc.
folgen dem gleichen Schema: Kategorisierung nach DIN-Methode + konkrete
Beispielphrasen.
