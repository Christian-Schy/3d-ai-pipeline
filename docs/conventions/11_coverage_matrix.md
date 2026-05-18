# 11 — Coverage-Matrix (Test-Aufbau pro Feature-Typ)

## Zweck

Diese Matrix definiert, **welche Wording-/Bezugs-Varianten ein Feature-Typ
abdecken muss**, damit eine Capability als "vollstaendig getestet" gelten
darf (Cov 3 fuer eine einzelne Feature-Klasse, Cov 4 fuer die Multi-
Capability-Stress-Goldens — siehe CLAUDE.md Capability-Matrix).

Sie verhindert "ad-hoc"-Test-Schreiben mit Luecken. Jede Feature-Konvention
(20-25) zieht ihre Test-Liste deterministisch aus dieser Matrix.

## Achsen

### Achse A — Bezugs-Methode (DIN, siehe [`10_masseintragung_din406.md`](10_masseintragung_din406.md))

| Code | Methode | Schema-Feld | Wording-Beispiel |
|---|---|---|---|
| **A1** | edge-to-CENTER | `edge_distances` (`abstand_*`) | "von linker Kante 25mm" |
| **A2** | edge-to-EDGE | `pocket_edge_distances` (`kante_*`) | "linke Taschen-Kante 25mm vom linken Rand" |
| **A3** | center-relativ | `center_offset` (`versatz_*`) | "10mm aus Mitte nach rechts" |
| **A4** | alignment | `alignment` | "zentriert", "mittig auf der Hoehe" |
| **A5** | Eck-Phrase = A1 (Ecken-Regel, zwei `abstand_*`) | `edge_distances` (zweikantig) | "in der oberen rechten Ecke der Face, 8mm nach links und 6mm nach unten versetzt" → `abstand_rechts: 8, abstand_oben: 6` |
| **A6** | "jeweils"-Regel | `edge_distances` (Mehrfach) | "jeweils 12mm von linker und vorderer Kante" | "jeweils von den kanten 10mm entfernt" |
| **A7** | Feature-zu-Feature-Bezug *(geplant Cap 6.0)* | TBD (Constraint-Bemassung) | "Bohrung 10mm vom Taschen-Rand", "zentriert ueber Slot" |

**Referenz-Objekt der A-Methoden:**
- **A1-A6** referenzieren in Capability 1.0 immer die **Bauteilkante**
  (Wuerfel/Platte). A2 (`kante_*`) misst die **Feature-eigene** Aussenkante
  zur Bauteilkante — heute aktiv fuer Tasche und Slot.
- **A5 = A1 (Eck-Wording-Variante):** "in der oberen rechten Ecke der
  Face, ... versetzt" zerfaellt per Ecken-Regel in zwei `abstand_*`-
  Kantenmasse — schema-maessig identisch mit A1. Kein eigenes Anker-
  Schema (siehe [`10_masseintragung_din406.md`](10_masseintragung_din406.md)
  Ecken-Regel + `data/prompts/conventions/anker.md`). Vorherige Lesart
  ("anchor + center_offset") ist zurueckgenommen 2026-05-18.
- **Bauteil-Face-Ecke vs Feature-Ecke:** A5 nutzt die **Bauteil**-Face-
  Ecke als sprachlichen Bezug. Phrasen wie "obere rechte Ecke **der
  Tasche** soll von oben 10mm entfernt sein" sind A2 (Feature-Kante als
  Mess-Bezug, zwei `kante_*`), nicht A5.
- **Ueberhang-Hinweis fuer ausgedehnte Features:** Bei A5 = A1 sitzt das
  Feature-CENTER auf den zwei `abstand_*`-Werten. Bei kleinen `abstand_*`
  und grossem Feature-Half ragt die Aussenkante ueber den Bauteilrand
  (Tasche, Slot, Plate). Wer eine **Eck-zu-Eck-Anlage mit definierter
  Restkante** will, schreibt **A2** (`kante_*`).
- **A7** referenziert eine **fremde** Feature-Kante / -Center ("Bohrung
  10mm vom Taschen-Rand entfernt"). Gehoert zu **Capability 6.0
  Constraint-Bemassung** und wird mit dieser Capability aktiviert — dann
  ergaenzen wir Matrix-Eintraege pro Feature-Typ (z.B. Bohrung-A7-zu-Tasche).
  Schema-Erweiterung folgt mit der Cap-6.0-Vorbereitung.

### Achse B — Achsen-Konfiguration

Eine Face hat 2 in-plane-Achsen (horizontal + vertikal). B beschreibt wie
viele und mit welcher Methoden-Mischung sie spezifiziert werden.

| Code | Konfig | Beispiel |
|---|---|---|
| **B0** | beide Achsen pure A4 (zentriert / kein Distanz-Mass) | "zentriert", "mittig", "soll zentral auf der mitte liegen" |
| **B1** | single-axis (eine Achse Methode A1-A3, andere Achse A4) | "mittig auf der Hoehe und von rechter Kante 20mm" |
| **B2** | dual-axis same-method (beide Achsen mit derselben A1/A2/A3) | "von linker Kante 25mm und von vorderer Kante 20mm" |
| **B3** | dual-axis mixed-method (z.B. X: A2 `kante_*`, Y: A1 `abstand_*`) | "rechte Taschen-Kante 20mm vom rechten Rand, 8mm von vorderer Kante" |

### Achse C — Rotation

| Code | Rotation | Anmerkung |
|---|---|---|
| **C0** | 0° (achsen-aligned) | Default |
| **C1** | 90°-Vielfaches | Nur Slot: triggert Length-Achsen-Swap, keine echte Rotation |
| **C2** | CCW positiv ≠ 90er | natuerliche Spec: "um 30° gedreht" (Default = CCW) |
| **C3** | CW negativ ≠ 90er | natuerliche Spec: "um 20° im Uhrzeigersinn gedreht" |

### Achse D — Wording-Reihenfolge (Demo-Varianz)

| Code | Reihenfolge | Beispiel |
|---|---|---|
| **D1** | Feature → Position | "Bohrung Ø8, von linker Kante 25mm" |
| **D2** | Position → Feature | "Von linker Kante 25mm eine Bohrung Ø8" |

D1 und D2 testen das **gleiche Resolved-Blueprint** — Wording-Robustheit
des Klassifizierers/Normalizers, nicht der Mathe.

## Pro Feature-Typ: Welche Zellen relevant

Tabelle pro Feature-Klasse: ✓ = Pflicht-Coverage, — = nicht anwendbar,
*(Anm.)* = mit Sonderfall.

| Feature | A1 | A2 | A3 | A4 | A5 | A6 | A7 | B0 | B1 | B2 | B3 | C0 | C1 | C2/C3 | Sonderfaelle |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Bohrung** ([20](20_bohrung_din.md)) | ✓ | — | ✓ | ✓ | ✓ | ✓ | ⏳ Cap 6.0 | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | point-like, keine Rotation, keine **eigene** Feature-Kante |
| **Tasche** ([22](22_tasche_din.md)) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ⏳ Cap 6.0 | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | volle Bezugs-Methodik + Rotation |
| **Nut/Slot** ([21](21_nut_slot_din.md)) | ✓ | ✓ | ✓ | ✓ | — | ✓ | ⏳ Cap 6.0 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ *(Konv.21 Edge-Case ≠ 90er)* | + Length/Width per-Achse, + 3 Richtungs-Wordings |
| **Pattern** ([24](24_pattern_din.md)) | ✓ | — | ✓ | ✓ | — | ✓ | ⏳ Cap 6.0 | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ *(Pattern-Rotation, nicht Kind-Bohrung)* | 3 Typen: Grid, Kreis, Linear-Reihe |
| **Plate** ([25](25_plate_din.md)) | ✓ | ✓ | ✓ | ✓ | ✓ | — | ⏳ Cap 6.0 | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | + Auflage-Face-Wahl, + Side-Stack, + Orientierung hochkant/flach |

Legende: ✓ = Pflicht-Coverage heute, — = nicht anwendbar, ⏳ = geplant mit der genannten Capability.

## Wording-Varianten pro Achse (Vokabular-Pool)

Pro Achse mehrere natuerliche Phrasen, damit der Klassifizierer/Normalizer
nicht auf ein einziges Wording festgenagelt wird.

### A4 (alignment) — Wording-Pool

| Variante | Beispiel |
|---|---|
| direkt | "zentriert", "mittig" | "zentral" |
| achsen-explizit | "mittig auf der Hoehe", "mittig in der Breite", "mittig in der Tiefe" |
| bündig | "rechtsbuendig", "linksbuendig", "oben anliegend" (`alignment: flush_*`) | "liegt auf der linken kante/seite an" |



### A1 (`abstand_*`) — Wording-Hinweis

**Trigger ist der Bezug, nicht das Wort.** Der User mischt im realen
Sprachgebrauch das Wort "versatz/versetzt" auch bei Kanten-Bezug:

| User-Phrase | Klassifizierer-Output |
|---|---|
| "10mm versatz von der linken Kante" | `abstand_links: 10` (A1) — Wort "versatz" ignoriert, Bezug=Kante zaehlt |
| "10mm aus der Mitte nach links versetzt" | `versatz_links: 10` (A3) — Bezug=Mitte zaehlt |

Klassifizierer-Prompt darf nicht das Wort "versatz" als A3-Trigger nehmen,
sondern muss am Bezugs-Wort ("Kante/Seite" → A1 vs. "Mitte" → A3)
entscheiden.

### A2 (`kante_*`) — Wording-Pool (ohne "deren")

| Variante | Beispiel |
|---|---|
| Feature-spezifisch | "rechte **Taschen-Kante** 25mm vom rechten Rand" |
| "mit" + Distanz | "rechte Taschen-Kante **mit** 25mm Abstand zur rechten Wuerfelkante" |
| anliegend (0-Distanz) | "Tasche **rechtsbuendig anliegend**" — semantisch identisch zu A4 `flush_right`; siehe Anm. unten |
| Feature-Ecke | "**obere rechte Ecke der Tasche** soll von oben 10mm und von rechts 20mm entfernt sein" (Feature-Ecke = 2 Feature-Kanten gleichzeitig) |
| Nut-Endpunkt | "**Nut-Endpunkt** 18mm von oberer Wuerfelkante" |

**Anm. "anliegend/buendig ohne Zahl":** Distanz=0 ist A4 (`alignment: flush_*`),
nicht A2. Wenn das LLM `kante_<dir>: 0` emittiert, normalisiert der Resolver
das automatisch auf flush. "anliegend X mm" ohne Zahl X gibt es nicht —
buendig **schliesst Offset aus** (bewusster User-Hinweis 2026-05-14).

**Anm. "obere/untere Feature-Kante":** Auf einer horizontal liegenden Face
(top/bottom) hat das Feature keine "obere/untere Kante" — nur 4 Seiten-
Kanten in-plane (links/rechts/vorne/hinten). "Obere Kante der Tasche"
sinnvoll nur auf Side-Faces (vorne/hinten/links/rechts) oder wenn Z-Tiefe
gemeint ist (das ist dann der Pocket-Boden, nicht A2).

"deren" + "die X-Kante der Tasche" sind erlaubt, aber **nicht** die einzige
Trigger-Form (Klassifizierer-Prompts duerfen darauf nicht konditioniert sein).

### Slot-Richtungs-Wording (Capability-21-spezifisch)

| Variante | Beispiel |
|---|---|
| Achsen-Bezug | "entlang Y-Achse", "entlang der X-Achse" |
| Richtungs-Verb | "verlaeuft nach hinten", "laeuft nach oben", "nach unten/links/rechts/oben" |
| Parallelitaet | "**parallel zur linken Kante/Seite**" (Slot-Length-Achse parallel zur genannten Bauteilkante) |
| Anfangs-/Endpunkt | "Anfangspunkt 20mm von linker Kante, Endpunkt 80mm von linker Kante" |

### Plate-Auflage / Orientierung (Capability-25-spezifisch)

| Variante | Beispiel |
|---|---|
| Auflage-Face explizit | "die **40x20-Flaeche** liegt auf", "es liegt die **30x80-Seite** auf" |
| Orientierung | "liegt **hochkant**", "liegt **flach**" |
| Side-Stack | "rechts daneben", "bündig anliegend" |

### Side-Face Wording-Konvention

Auf **Side-Faces** (vorne/hinten/links/rechts) hat der User in seinem 2D-
Bildschirm-Mental-Modell (siehe `user_orientation_mental_model.md`) eine
Kollision zwischen Cube-Global-Terms und Face-Local-Terms:

- **"oben/unten"** funktioniert identisch (vertikal auf Face = Z)
- **"links/rechts"** → **face-local** horizontale Richtung (mit LUT-Flip
  auf <X- und >Y-Faces; siehe `project_face_viewing_convention.md`)
- **"vorne/hinten"** → kollidiert im 2D-Modell oft mit "oben/unten" und
  ist deshalb **mehrdeutig** auf Side-Faces

Konvention fuer Spec-Wordings auf Side-Faces:

| Bevorzugt (Side-Face) | Vermeiden (Side-Face) |
|---|---|
| "von oberer Kante 10mm und von rechter Kante 20mm" | "von oberer Kante 10mm und von hinterer Kante 20mm" (Kollision oben+hinten) |
| "10mm aus Mitte nach oben und 5mm aus Mitte nach rechts" | "10mm aus Mitte nach oben und 5mm aus Mitte nach hinten" (gleiche Kollision) |
| "mittig auf der Hoehe und von linker Kante 18mm" | "mittig auf der Hoehe und von vorderer Kante 18mm" |

Auf **Top-/Bottom-Faces** (oben/unten) ist alles erlaubt — da ist
horizontal direkt Cube-X (links/rechts) und vertikal direkt Cube-Y (vorne/
hinten), keine Mehrdeutigkeit.

**Bekannte Fixes nach dieser Konvention:** H06 (rechts, oben+rechts statt
oben+vorne), N11 (links, Hoehe+rechts statt Hoehe+vorne), T05 (links,
analog), T06 (rechts, oben+links statt oben+vorne).

## Workflow fuer Test-Listen-Erstellung

1. Pro Feature: aus obiger Tabelle die ✓-Zellen ablesen.
2. Pro relevanter Zelle min. **1 Spec-Text** schreiben mit den natuerlichsten
   Wording-Varianten aus den Pools oben.
3. Zu mindestens 50% der Specs eine **D2-Variante** erzeugen (Reihenfolge
   gespiegelt), aber **gleiches** Resolved-Blueprint erwartet.
4. Spec-Liste ergibt typischerweise 8-12 Zeilen pro Feature-Typ, plus
   D2-Varianten ~16-24 Test-Cases.
5. Edge-Cases (z.B. Tasche-ueberragt-Wuerfel, Slot-Rotation ≠ 90er)
   bekommen einen eigenen STRESS-Test, **nicht** in Coverage.

## Hinweis: Per-Zelle nur EIN Beispiel-Wording

In den Wording-Pool-Tabellen oben und in den Feature-Konvention-Dokuen
(20-25) steht **pro Zelle in der Regel nur ein Beispiel-Spec**. Das ist
**ein** repraesentatives Wording — der Klassifizierer/Normalizer muss
aequivalente Phrasen ebenfalls korrekt klassifizieren. Coverage zaehlt die
**Matrix-Zelle**, nicht das einzelne Wording.

## Was diese Matrix NICHT abdeckt

- **Multi-Feature in einem Teil** (mehrere Bohrungen + Tasche + Slot):
  ist **kombinatorisch aus dieser Matrix ableitbar** — eine Multi-Feature-
  Spec ist einfach mehrere Single-Feature-Phrasen aneinandergereiht. Eigene
  STRESS-Goldens in Cap 1.0 Cov 4 testen das (mehrere Features pro Run,
  identische Single-Feature-Lesart). Keine zusaetzliche Matrix-Achse
  noetig.
- **Multi-Part** (mehrere Platten/Teile) → P-Stack3 Plate-on-Plate-on-Plate
  → STRESS.
- **Toleranzen, Senkungen, Gewinde** → Capability 4.0/7.0, eigene
  Konvention-Dokus 30/40.
- **Constraint-Bemassung Feature-zu-fremder-Feature** → Capability 6.0
  (zukuenftige Achsen-Erweiterung A7).

## Eigene Wording-Beispiele (User-Pool, ergaenzen erwuenscht)

Hier sammeln wir **echte Konstrukteur-Phrasen** pro Matrix-Zelle. Jeder
Eintrag wird automatisch zu einem Demo-Kandidaten fuer DSPy/Klassifizierer-
Training und kann in die Test-Specs der Feature-Dokus (20-25) wandern.

Format: einfacher Listen-Eintrag, optional mit Quelle (Run-ID, Datum, oder
"erfahrungsbasiert").

### A1 — `abstand_*` (edge-to-CENTER)
- von der linken seite/kante 10mm entfernt
- versatz von der oberen kante/seite von 20mm  *(Wort "versatz" + Kanten-Bezug → A1, siehe A1-Wording-Hinweis oben)*
- um 20mm von der rechten seite/kante versetzt  *(Wort "versetzt" + Kanten-Bezug → A1)*
- von der linken seite um 30mm entfernt
- von der vorderen seite um 20mm versetzt  *(Wort "versetzt" + Kanten-Bezug → A1)*
- 20mm von der unteren seite/kante entfernt
- 10mm versatz von der linken seite/kante  *(Wort "versatz" + Kanten-Bezug → A1)*

### A2 — `kante_*` (edge-to-EDGE)
- die linke kante der tasche/würfel/platte soll von der linken seite 10mm entfernt sein
- die rechte seite der tasche/würfel/platte soll von der rechten kante 20mm entfernt sein
- die untere seite [des Bauteils] soll von der unteren kante der tasche/würfel/platte 20mm entfernt sein
- die rechte seite der tasche/würfel/platte soll von der rechten seite/kante der/des platte/würfels 10mm entfernt sein
- obere kante der tasche/würfel/platte soll von oben 10mm entfernt sein  *(war in A1, ist A2 weil Feature-Kante explizit)*
- von der rechten seite 20mm entfernt die rechte seite/kante der tasche/würfel/platte  *(war in A1, ist A2)*
- die obere rechte ecke der tasche soll von oben 10mm entfernt sein und von rechts 20mm  *(Feature-Ecke = 2 Feature-Kanten gleichzeitig)*
- die rechte untere ecke des würfels soll von der rechten unteren ecke der tasche jeweils 10mm entfernt sein  *(Feature-Ecke vs Bauteil-Ecke)*

*Edge-Case (siehe A2-Anm. oben):* "die obere seite der tasche soll von der
hinteren seite 10mm entfernt sein" — auf einer horizontalen Top-Face hat
die Tasche keine "obere Seite" als 2D-Edge. Phrase ist nur auf Side-Faces
sinnvoll.

### A3 — `versatz_*` (center-relativ)
- soll von der mitte um 10mm nach oben und 20mm nach rechts versetzt werden
- soll ein abstand von der mitte nach links von 10mm haben
- abstand von der mitte nach rechts 20mm
- 20mm nach links von der mitte
- 30mm versatz nach unten von der mitte
- nach unten von der mitte um 10mm

### A4 — `alignment` (zentriert / buendig)
- soll oben bündig anliegen
- soll auf der rechten seite/kante bündig anliegen
- bündig zur unteren seite/kante
- soll auf der y-achse zentriert werden  *(single-axis, gehoert eigentlich zu B1 wenn die andere Achse spezifiziert ist; pur ist es A4)*
- soll auf der oberen kante zentriert werden  *(zentriert in der Achse parallel zur oberen Kante)*

### A5 — Eck-Phrasen-Wording (numerisch = A1)
- "Bohrung in der oberen rechten Ecke der Face, 8mm nach links und 6mm nach unten versetzt" → `abstand_rechts:8, abstand_oben:6`
- "Tasche in der unteren linken Ecke, 12mm und 15mm versetzt" → `abstand_unten:15, abstand_links:12`

*Hinweis 1:* A5 ist kein eigenes Schema — Eck-Phrasen werden per Ecken-
Regel in zwei `abstand_*`-Kantenmasse aufgeloest. Numerisch identisch mit
A1.

*Hinweis 2:* Feature-Ecke-Phrasen ("obere Ecke **der Tasche** ...") sind
A2 (`kante_*`), nicht A5. A5 nutzt **Bauteil-Face-Ecke** als
sprachlichen Bezug.

*Hinweis 3:* Wenn das Feature sauber **innerhalb** der Bauteilkante
liegen soll (Standard-Erwartung), `kante_*` (A2) waehlen — Eck-zu-Eck-
Anlage mit definierter Restkante.

### A6 — "jeweils"-Regel
- jeweils von den seiten/kanten 20mm entfernt
- jeweils eine entfernung von 10mm von der rechten oberen ecke haben  *(A5 Bauteil-Anker + A6 jeweils)*
- von der hinteren rechten ecke jeweils 20mm entfernt  *(war in A1, ist A5+A6 Kombination)*
- von der oberen linken ecke oben 20mm und links 10mm entfernt  *(A5 Bauteil-Anker, explizite Achsen-Werte statt "jeweils")*
- von der unteren rechten ecke um 20mm nach links und um 10mm nach oben versetzt  *(A5 Bauteil-Anker + Versatz)*

### A7 — Feature-zu-Feature *(Cap 6.0, schon mal sammeln)*
- (frei)

### B0 — beide Achsen pure A4 (zentriert)
- soll zentral auf der mitte liegen
- soll zentriert sein
- mittig auf der Face

### B1 — single-axis (eine Achse alignment, andere A1-A3)
- soll zentral auf der x-achse liegen und um 10mm nach links versetzt werden  *(X = A4 zentral, Y? — User-Phrase ist mehrdeutig; vermutlich meinte User: X-Achse zentral UND auf der gleichen X-Achse 10mm versatz; oder: zentral auf X + Y-Versatz)*
- mittig auf der hoehe und von rechter kante 20mm  *(Y = A4 mittig, X = A1)*

### B2 — dual-axis same-method
- von der linken seite 10mm entfernt und von der oberen seite 20mm entfernt  *(beide A1)*
- soll von der mitte um 10mm nach oben und 20mm nach rechts versetzt werden  *(beide A3)*
- die linke kante 10mm vom linken rand, die obere kante 15mm vom oberen rand  *(beide A2)*

### B3 — dual-axis mixed-method
- obere kante der tasche soll von oben 10mm entfernt sein und um 10mm aus der mitte nach links versetzt  *(Y = A2, X = A3)*
- rechte taschen-kante 20mm vom rechten rand, 8mm von vorderer kante  *(X = A2, Y = A1)*

### C2/C3 — Rotation
- soll um 20 grad im uhrzeigersinn gedreht werden  *(C3)*
- soll gegen uhrzeigersinn um 10 grad gedreht werden  *(C2)*
- soll um 20 grad im uhrzeigersinn rotiert werden  *(C3, Verb-Variante)*
- soll eine rotation um 10 grad im uhrzeigersinn haben  *(C3, Substantiv-Variante)*

### Slot-Richtung
- entlang der x-achse
- entlang der y-achse
- parallel zur linken kante/seite  *(hochgeholt in Slot-Richtungs-Pool oben)*
- nach unten/links/rechts/oben

### Plate-spezifisch (Auflage-Face / Side-Stack / Orientierung)
- die 40x20 fläche liegt auf  *(hochgeholt in Plate-Pool oben)*
- es liegt die 30x80 seite auf
- liegt hochkant
- liegt flach

### Multi-Feature-Beispiele (Verkettung mehrerer Single-Specs)
- (frei — Beispiel: "Wuerfel 120x90x50. Oben eine Bohrung Ø8 von linker Kante 25mm und von vorderer Kante 20mm. Vorne eine Tasche 30x20x10 zentriert. Rechts eine Nut 5x3 40mm lang entlang Z, von oberer Kante 15mm.")

*Hinweis Cap 6.0:* Pronominal-Bezuege ("daneben noch eine Bohrung",
"gegenueber davon eine Tasche") und Plurale ("vier Bohrungen rund um die
Tasche") sind **nicht** in Cap 1.0 abgedeckt — sie brauchen Feature-zu-
Feature-Aufloesung (A7) und gehoeren zu Cap 6.0 / STRESS.

## Stand

Aktiv seit 2026-05-14. Pilot: Bohrung ([20_bohrung_din.md](20_bohrung_din.md)).
Tasche/Slot/Pattern/Plate folgen analog nach Pilot-Approval.
