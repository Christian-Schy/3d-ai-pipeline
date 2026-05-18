# 98 — Engineering-Capabilities-Plan (Roadmap fuer Cap 1.5-8.0)

Stand: 2026-05-18.

Dieses Dokument ist der konkrete **Bau-Plan** fuer die Engineering-Elemente,
die `99_normen_audit.md` als Luecken identifiziert hat — gegliedert nach
der Capability-Leiter aus [CLAUDE.md](../../CLAUDE.md).

Trennung der beiden Plan-Docs:

- [`99_normen_audit.md`](99_normen_audit.md) — *Bestandsaufnahme*: was
  heute fehlt, wo Doku-/Code-Stand kollidiert.
- `98_engineering_plan.md` (dieses Doc) — *Roadmap*: pro zukuenftiger
  Capability, was konkret gebaut werden muss, mit Norm-Anker, Schema-
  Erweiterungen und Klassifizierer-/Template-/Test-Aufwand.

Die Konventions-Bibliothek (10-26) bleibt **Single Source of Truth** fuer
das *aktuell Implementierte*. Wenn eine Capability hier umgesetzt wird,
wandert die jeweilige Konvention in ein eigenes Doc (30, 31, 40, 50, 60)
und wird aus diesem Plan rausgenommen.

---

## Cap 1.0 — Quick-Wins (vor Cap-Sprung sauber abschliessen)

Diese Punkte schliessen die aktive Capability 1.0 sauber ab; kein
Capability-Sprung noetig.

| Item | Wo | Aufwand |
|---|---|---|
| ~~**Slot-Template Endradien** (`R = Breite/2`)~~ ✅ erledigt 2026-05-18 (Paket 4) | `src/codegen/templates.py` `slot`-Template | — |
| ~~**Slot-Restwandstaerke-Validator** (Aussenkontur → Bauteilkante ≥ Mindest)~~ ✅ erledigt 2026-05-18 (Paket 4) | `src/tools/coordinate_validator.py` Check 11 | — |
| **Pattern `start_angle_deg`-Vokabular** ("erste Bohrung bei 0°/90°") | `prompt_classifier_circular.py` + Demos | klein |
| **Pattern Kind-Bohrung-Validation** (jede Bohrung im Pattern gegen Bauteilrand) | `coordinate_validator.py` | mittel |
| **Tasche rotiert: exakte Konturpruefung** statt bbox-Approximation | `coordinate_validator.py` | mittel |
| **Edge-Features Innen-/Aussenkanten-Filter** ("Aussenkanten der Top-Face ohne Tasche-Kanten") | Template + Klassifizierer | mittel |
| **Edge-Features E2-Coverage** ("horizontale Kanten") | Goldens + Klassifizierer-Demos | klein |
| ~~**Slot-Pipeline-Goldens-Heatmap** unter Mittellinien-Regel verifizieren~~ ✅ erledigt 2026-05-18 (Paket 1.5) | Ollama-Heatmap-Run | — |
| **NEST `hole_classifier`-Fix** (Ecken-Regel `abstand_*` statt `versatz_*`) | Prompt/Demo + Retrain | mittel, GPU |

---

## Cap 2.0 — Modifications (CLAUDE.md Reihenfolge-Punkt 2)

Bestehend per Coder-Pfad; Plan: in Templates ueberfuehren.

- Fasen/Rundungen alle Kanten-Auswahl-Varianten als Templates (E0-E5).
- Asymmetrische Fase (`C2×3`, ≠ 45°) — Template-Erweiterung
  `chamfer(length, length2, angle)`.
- Shell-Operation (`.shell(thickness)`) — Template.
- Reihenfolge-Validator (Fasen vor Rundungen).

Norm-Anker: ISO 129-1 (Maßeintragung); separat ISO 13715 fuer
Kantenzustand (Cap 7.0).

---

## Cap 4.0 — Connections (Senkungen, Gewinde, Stufenbohrungen)

Hoher B2B-Wert; bringt den ersten Schritt Richtung Konstrukteur-Workflow.

### Norm-Anker

- DIN EN ISO 273 — Durchgangsloecher fuer Schrauben
- DIN ISO 4762 — Zylinderschrauben mit Innensechskant
- DIN EN ISO 10642 — Senkschrauben
- DIN 13 / ISO 261 — Metrisches ISO-Gewinde
- DIN 76, DIN 509 — Gewinde-Auslauf, Freistich
- DIN EN ISO 15065 — Senkungen fuer Senkschrauben

### Schema-Erweiterungen (additiv zu `hole_single`)

```yaml
hole_single:
  params:
    diameter: 8
    depth: 20            # bestehend
    through: false       # NEU: durchgangs vs Sackloch (explizit)
    thread: "M8"         # NEU: ISO-Gewinde-Bezeichnung
    counterbore:         # NEU: Zylindersenkung
      diameter: 14
      depth: 8
    countersink:         # NEU: Kegelsenkung
      angle_deg: 90
      diameter: 16
    step:                # NEU: Stufenbohrung
      - {diameter: 12, depth: 10}
      - {diameter: 8,  depth: 20}
```

### Klassifizierer-Wording

- "M8 Sackloch 20 tief"
- "M6 durchgehend"
- "Zylindersenkung fuer M6" (impliziert counterbore-Default)
- "90 Grad Senkung Durchmesser 16"
- "Stufenbohrung: oben 12 5 tief, unten 8 durchgehend"

### Templates

- Erweitertes `hole_single`-Template, das `thread` / `counterbore` /
  `countersink` / `step` rendert.
- Optional: echte Gewinde-Helix (`cq.Solid.makeHelix`) fuer STEP/2D-Output;
  vereinfacht zur Durchgangs-Bohrung mit Annotation fuer STL.

### Tests

- Coverage: 4 Bohrungstypen × {durchgangs, Sackloch} × Standard-Größen.
- STRESS: Bohrung mit kombinierten Features (Gewinde + Senkung + Stufung).

---

## Cap 5.0 — Assemblies (bewegliche Teile, Mate-Constraints)

### Norm-Anker

- ISO 16792 — Model-Based Definition (3D-Assembly-Constraints)

### Schema-Erweiterungen

- `mate`-Constraint zwischen Feature-Paaren: `coincident`, `parallel`,
  `concentric`, `tangent`, `distance(value)`.
- Bewegliche Teile: degrees of freedom (z.B. Drehgelenk um Achse).

### Assembler-Erweiterung

- **JoinAssembler** (CLAUDE.md "Multi-Assembler"): Teile bleiben getrennte
  Bodies und werden ueber definierte Anschlussflaechen verbunden
  (CadQuery `Assembly`-API statt `Union`).

### Klassifizierer-Wording

- "Plattenstapel mit Spalt 5mm"
- "Scharnier-Stift Ø6 durch beide Platten"
- "Achse drehbar um die Z-Achse"

---

## Cap 6.0 — Constraint-Bemassung (Datums + A7 Feature-zu-Feature)

### Norm-Anker

- **DIN EN ISO 5459:2025-12** — Datums und Datum-Systeme (3. Ausgabe)
- DIN EN ISO 129-1:2022-02 — Koordinatenbemassung (Section 9)

### Schema-Erweiterungen

```yaml
teil:
  datum:               # NEU: Bauteil-Bezugssystem
    a: ">Z"            # primaerer Datum (Flaeche/Achse)
    b: "<X"            # sekundaer
    c: "<Y"            # tertiaer

feature:
  position:
    reference:         # NEU: Bezug statt Bauteilkante
      datum: "A"       # ODER:
      feature: "tasche_oben_0"
      point: "right_edge"
    abstand_<datum>: 25   # statt abstand_links: 25
```

### Klassifizierer-Wording

- "Datum A = obere Flaeche, Datum B = linke Kante"
- "Bohrung 25mm von Datum A"
- "Bohrung 10mm vom Taschenrand" (A7)
- "zentriert ueber Slot" (A7)
- "Position bezogen auf A|B|C"

### Coverage-Matrix

- **A7 Spalte aktivieren** (heute "⏳ Cap 6.0" markiert in
  [`11_coverage_matrix.md`](11_coverage_matrix.md)).
- Pro Feature-Typ A7-Wording-Pool.

### Zusatz: Symmetrie + Koordinatenbemassung + Auto-Close

- Symmetrie-Constraint ("symmetrisch zur X-Achse" → Spiegelung).
- Koordinaten-Tabelle ("X=25, Y=40 ab Bezug A/B").
- Auto-Close fuer Kontur (Cap 1.5).

---

## Cap 7.0 — Engineering Norms (Toleranzen + GD&T + Kantenzustand + Norm-Bauteile)

DAS Verkaufsmerkmal fuer B2B-Maschinenbau. Eng verzahnt mit Cap 6.0
(Datums sind Voraussetzung fuer GD&T).

### Norm-Anker

- **DIN EN ISO 286-1/-2:2019** — ISO-Code-System Passungen (H7/g6 etc.)
- **DIN EN ISO 1101:2017** — Form-/Richtungs-/Orts-/Lauf-Toleranzen (GD&T)
- **DIN EN ISO 13715:2020-01** — Werkstueck-Kanten unbestimmter Gestalt
  (Symbole `±`/`-`/`+`)
- DIN EN ISO 14405-1 — Linear-Toleranzen
- DIN 13 (Gewinde-Passungen), DIN 76, DIN 332 — Norm-Bauteile

### Schema-Erweiterungen

```yaml
# Pro Mass-Wert optional Toleranz
params:
  diameter:
    nominal: 8
    tolerance: "H7"           # ISO 286 Passklasse
    # ODER explizit:
    tolerance_plus: 0.018
    tolerance_minus: 0

# GD&T-Spec pro Feature
gdt:
  - type: "position"          # ⌖
    zone: 0.1
    datums: ["A", "B", "C"]
  - type: "perpendicularity"  # ⊥
    zone: 0.05
    datum: "A"

# Kantenzustand pro Kanten-Auswahl
edge_state:
  selector: ">Z"
  state: "+0.5"               # Grat bis +0.5mm erlaubt
  # oder: "sharp", "rounded", "+/-0.3"
```

### Klassifizierer-Wording

- "Bohrung Ø10 H7"
- "Rechtwinkligkeit 0.05 zu Datum A"
- "Positionstoleranz 0.1 zu A|B|C"
- "Kantenzustand +0.5 an oberen Aussenkanten"

### Templates / Output

- STL-Geometrie wird durch Toleranzen NICHT veraendert (STL hat keine
  Toleranzinformation).
- **STEP-Export (Cap 8.0)**: Toleranzen als PMI (Product Manufacturing
  Information) im AP242-Modell.
- **2D-PDF-Output (Cap 8.0)**: Maßlinien mit Toleranzangaben + GD&T-
  Rahmen.

### Norm-Bauteile-Bibliothek

- Eigene Component-Library: DIN-933 (Sechskantschraube), DIN-7984
  (Zylindersenkschraube), DIN-EN-ISO-4762 (Innensechskantschraube),
  DIN-6325 (Zylinderstift), DIN-625 (Rillenkugellager), ...
- Klassifizierer erkennt Norm-Bezeichnung ("M8x25 DIN 933") und Resolver
  greift auf Norm-Tabelle zu — kein freier Parameter-Bau.
- Templates rendern aus tabellarischen Norm-Daten.

---

## Cap 8.0 — Professional Output (STEP / DXF / 2D-PDF / DFM)

### Norm-Anker

- **ISO 10303-242 (STEP AP242)** — 3D mit MBD/PMI
- ISO 128-Reihe — 2D-Zeichnung
- DIN EN ISO 5455 — Massstaebe

### Output-Formate

- **STEP AP242 (Pflicht):** 3D mit PMI — Toleranzen, Datums, GD&T-
  Symbole sind im Modell eingebettet. Das ist das **B2B-Liefer-Format**.
  CadQuery + OCCT exportieren STEP nativ; PMI-Annotation ist eine
  Erweiterung.
- **DXF:** 2D-Ansichten (Frontansicht, Draufsicht, Seite). CadQuery
  unterstuetzt 2D-Projektion via OCCT.
- **PDF:** 2D-Werkstattzeichnung — Massstab, Massketten, Toleranzen,
  Stueckliste. Aufwendig, eigener Layout-Schritt.
- **STL:** bestehend (Default-Output heute).

### DFM-Checks (Design for Manufacturing)

- Mindestwandstaerken (material-spezifisch).
- Werkzeug-Zugang (Senkungen brauchen 90°-Zugang etc.).
- Hinterschnitte (fuer Spritzguss/Druckguss).
- Bohrungs-Aspektverhaeltnis (max. 10:1 fuer Standardwerkzeug).

---

## Cap 3.0 / 1.5 — Komplexe Formen / Extended Primitives

Diese sind in CLAUDE.md beschrieben (Multi-Assembler, ContourSpecifier-
Agent). Hier nur die Norm-Anker:

- ISO 128 (Schnittdarstellung — wichtig fuer Hohlraeume).
- Allgemein: ISO 129-1 fuer Bemassung der Kontur-Punkte.

Details siehe CLAUDE.md "Architektur-Notizen fuer spaeter".

---

## Reihenfolge-Empfehlung

CLAUDE.md hat eine Reihenfolge 1.0→2.0→6.0→1.5→4.0→7.0→8.0→3.0→5.0→9.0.
Aus B2B-Sicht (Verkaufsziel) waere ein leicht angepasster Pfad sinnvoll:

1. **Cap 1.0 Quick-Wins** abschliessen (Endradien, Pattern-start_angle,
   NEST-Klassifizierer-Fix, Heatmap-Verifikation).
2. **Cap 2.0 Modifications** (Templates statt Coder).
3. **Cap 4.0 Connections** — bringt sofortigen B2B-Wert (Senkungen,
   Gewinde sind die haeufigsten "fehlt mir das" beim Konstrukteur).
4. **Cap 6.0 Constraint-Bemassung (Datums + A7)** — Voraussetzung fuer
   Cap 7.0.
5. **Cap 7.0 Toleranzen + GD&T** — der eigentliche B2B-Verkaufstreiber.
6. **Cap 8.0 STEP-Export mit PMI** — parallel zu 7.0 sinnvoll, weil PMI
   ohne Datums/Toleranzen leer waere.
7. **Cap 1.5 Extended Primitives** (Polygon, Kontur-Extrude) — wann
   gebraucht.
8. **Cap 5.0 Assemblies** — komplex, eher spaet.
9. **Cap 3.0 Komplexe Formen / Cap 9.0 Vision** — letzte Stufen.

Diese Reihenfolge konzentriert sich darauf, einen Konstrukteur moeglichst
schnell *normgerecht* arbeiten zu lassen — Cap 4+6+7+8 bilden zusammen den
B2B-Workflow ab.

---

## Verzaehnung mit Konventions-Bibliothek-Slots

Die README-Tabelle in [`README.md`](README.md) listet TBD-Eintraege
30, 31, 40, 50, 60. Wenn eine Capability hier umgesetzt wird, entsteht
das jeweilige Konvention-Doc:

| Cap | Konvention-Doc |
|---|---|
| 4.0 Senkungen/Gewinde | (neu) `40_normbauteile_din.md` Teil 1 + `41_gewinde_iso261.md` |
| 6.0 Datums + A7 | (neu) `50_constraint_bemassung_iso5459.md` |
| 7.0 ISO 286 Passungen | (TBD-Slot) `30_toleranzen_iso286.md` |
| 7.0 ISO 1101 GD&T | (TBD-Slot) `31_gdt_iso1101.md` |
| 7.0 ISO 13715 Kantenzustand | (neu) `32_kantenzustand_iso13715.md` |
| 7.0 Norm-Bauteile DIN | (TBD-Slot) `40_normbauteile_din.md` Teil 2 |
| 8.0 STEP/PDF/DXF | (TBD-Slot) `60_step_export_ap242.md` |

## Quellen

- [`99_normen_audit.md`](99_normen_audit.md) — Bestandsaufnahme der
  Luecken, die in diesen Plan gemuendet sind.
- [`CLAUDE.md`](../../CLAUDE.md) — Capability-Matrix + Architektur-
  Notizen fuer spaeter.

## Stand

Plan-Doc neu (2026-05-18) als Abschluss des Konventions-Walkthrough-
Pakets. Wird aktualisiert sobald eine Capability gestartet wird.
