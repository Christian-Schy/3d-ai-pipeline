# ADR 0008 — Capability×Coverage Matrix als Projekt-Struktur

- **Datum:** 2026-05-14
- **Status:** accepted
- **Vorgaenger-ADRs:** keine direkt; ersetzt die lineare "Phase 1-4"-Struktur in CLAUDE.md
- **Verwandt:** Memory `project_next_phase_plan.md`, `project_phase_1_abschluss.md`

## Problem

CLAUDE.md hat das Projekt bisher in zwei vermischten Achsen organisiert:

1. **Stufenplan** (Stufe 1-4: was die Pipeline kann — Primitive Assembly,
   Verbindungen, Komplexe Formen, Organisch).
2. **Phasen 1-4** (lineare Arbeitsphasen — Phase A 3-Step-Chain, Phase B
   Geometry Assertions, Phase C Verbindungen, Phase D Komplexe Formen,
   Phase E Vision).

Die Vermischung erzeugt mehrere Probleme:

- "Fasen+Rundungen ausbauen" steht in der Phase-1-Abschluss-Liste
  (Punkt 5), ist aber semantisch eine eigene Capability (Modifications),
  nicht ein Implementierungs-Detail von Stufe 1.
- "Funktion bauen" und "Funktion mit Tests absichern" sind heute zwei
  verschiedene Phasen (Phase A vs. Phase B). Konsequenz: gebaute
  Capabilities werden als "fertig" markiert, lange bevor sie wirklich
  unter Last (Multi-Feature, alle Seiten, Edge-Cases) stabil sind.
- Neue Capabilities (Constraint-Bemassung, Polygon-Extrusionen,
  Auto-Closing-Contours, Toleranzen, GD&T, STEP-Export) lassen sich nicht
  sauber in die heutige Phasen-Liste einsortieren — sie sind weder
  Phase-1-Abschluss noch klar einer Phase B/C/D/E zugeordnet.
- Verkaufsziel ist B2B Maschinenbau-CNC-Konstrukteur. Damit wird die
  Engineering-Konvention (DIN/ISO) zum harten Akzeptanz-Kriterium pro
  Capability — nicht zu einem nachgelagerten Polish-Schritt.

Die heutige Struktur skaliert nicht fuer ein professionelles Produkt.

## Entscheidung

Wir ersetzen die lineare Phasen-Struktur durch eine **Capability ×
Coverage Matrix**. Die Matrix ist die Single Source of Truth fuer "wo
stehen wir" und "was kommt als naechstes".

### Achse 1 — Capabilities (was die Pipeline kann)

Capabilities sind orthogonal organisierte Faehigkeits-Stufen. Eine
Capability ist eine in sich geschlossene Faehigkeits-Einheit; sie hat
eine eigene DIN/ISO-Konvention, eigene Templates, eigene Demos und
eigene Goldens.

| Stufe | Capability | Beispiel-Inhalt |
|---|---|---|
| 1.0 | Primitive Assembly | Box/Zylinder + Bohrung/Nut/Tasche/Patterns |
| 1.5 | Extended Primitives | Polygon (3/4/6/8-eck), Trapez, Kontur-Extrude/Pocket, Auto-Closing-Contours |
| 2.0 | Modifications | Fasen/Rundungen aller Kanten-Auswahl-Varianten als Templates, Shell |
| 3.0 | Komplexe Formen | Loft, Sweep, Spline, Revolve |
| 4.0 | Connections | Senkbohrungen (Counterbore/Countersink), Gewinde, Durchgangs-Bohrung durch zwei Teile |
| 5.0 | Assemblies | Bewegliche Teile (Join statt Merge), kinematische Constraints |
| 6.0 | Constraint-Bemassung | Origin/Datum, Absolut X/Y/Z, Symmetrie, Feature-zu-Feature-Bezug, Auto-fill fehlender Masse |
| 7.0 | Engineering Norms | Toleranzen ISO 286, GD&T ISO 1101, Norm-Bauteile-Bibliothek (DIN-Schrauben/Lager/Stifte) |
| 8.0 | Professional Output | STEP/IGES, DXF, 2D-Zeichnungs-PDF, DFM-Checks, Material/Gewicht |
| 9.0 | Vision/Drawing Input | Bild oder technische Zeichnung → Blueprint |

Die Liste ist additiv erweiterbar — neue Capabilities bekommen eine
neue Stufen-Nummer. Lueckenhafte Nummerierung (1.0/1.5) ist erlaubt
wenn es semantisch passt.

### Achse 2 — Coverage (Test-Robustheit pro Capability)

| Cov | Definition |
|---|---|
| 0 | Nichts implementiert oder nicht getestet |
| 1 | Component-Goldens grün (Splitter + Resolver isoliert pro Sub-Layer) |
| 2 | Pipeline-Goldens Basics grün (Real-Run, einfacher Case pro Variante) |
| 3 | Coverage-Goldens grün (eine Capability komplett — alle Seiten, alle Wording-Varianten in einem Test) |
| 4 | Stress-Goldens grün (Multi-Capability-Kombo, ~20+ Features in einem Teil) |
| 5 | Limit-Tests grün (50+ Features, 8+ Plates, Pipeline-Robustheit) |
| 6 | Real-World Engineering-Validation (extern getestet von Konstrukteur-User) |

### Definition of Done

Eine Capability ist **"fertig"** wenn **Cov 4 grün** ist UND die
folgenden Done-Review-Punkte abgehakt sind. Cov 5 und Cov 6 sind
Polish-Stufen und nicht zwingend fuer "fertig", aber zwingend fuer
"verkaufsreif".

### Done-Review-Checkliste

Vor jedem "Capability X.Y done" Haken:

**Funktional**
- [ ] L1 Component-Goldens grün (Splitter + Resolver isoliert)
- [ ] L2 Coverage-Golden grün (alle Varianten alle Seiten in einem Test)
- [ ] L3 STRESS-Golden grün (Multi-Capability-Kombo)
- [ ] DSPy-Demos fuer alle wichtigen Patterns vorhanden

**DIN/ISO**
- [ ] `docs/conventions/<XX>_<capability>.md` geschrieben — Konvention dokumentiert
- [ ] Wording-Beispiele in `docs/conventions/90_user_wording_examples.md` ergaenzt
- [ ] Geometrische Korrektheit nach DIN-Norm verifiziert

**Code-Qualitaet**
- [ ] `make audit` grün (Dopplungen, Datei-Groesse, toter Code)
- [ ] Type-Hints in neuem Code
- [ ] Keine Funktion >50 LOC, keine Datei >500 LOC ohne ADR-Begruendung
- [ ] Modulare Verantwortungen (eine Datei → eine Sache)
- [ ] **Simplification-Pass durchgelaufen** — `/simplify` Skill auf
  geaenderten Code; jede Funktion gefragt "geht das kuerzer/klarer bei
  gleicher oder besserer Qualitaet?". Lange Funktionen die NICHT
  kleiner gehen brauchen einen Begruendungs-Kommentar.

**Schema/Doc**
- [ ] Schema additiv erweitert (nichts umbenannt/geloescht)
- [ ] CHANGELOG-Eintrag mit Commit-Hash
- [ ] ADR wenn Architektur-Entscheidung
- [ ] CLAUDE.md Capability-Matrix aktualisiert

**UX (Konstrukteur-Sicht)**
- [ ] Wording orientiert sich an Konstrukteur-Sprache, nicht CAD-Code
- [ ] Fehler-Meldungen verstaendlich fuer Profi-User
- [ ] Beispiel-Eingaben aus realen technischen Zeichnungen getestet

### Empfohlene Reihenfolge der Capabilities

Optimiert fuer maximale B2B-Konstrukteur-Wert pro Aufwand:

1. **1.0 Cov 4** — Primitive Assembly STRESS abschliessen
2. **2.0** — Modifications (Fase/Rundung) komplett (Templates + Goldens)
3. **6.0** — Constraint-Bemassung (DAS unterscheidet Maker- vom Konstrukteur-Tool)
4. **1.5** — Extended Primitives + Auto-Close
5. **4.0** — Connections (Senkungen, Gewinde, Cross-Part)
6. **7.0** — Engineering Norms (Toleranzen) — Verkaufs-Polish
7. **8.0** — Professional Output (STEP) — Verkaufs-Notwendigkeit
8. **3.0** — Komplexe Formen (Loft/Sweep)
9. **5.0** — Assemblies
10. **9.0** — Vision/Drawing Input

## Verworfene Alternativen

### Lineare Phase 1-4 (heutige Struktur) beibehalten

Verworfen weil sie "bauen" und "absichern" trennt, was zu Pseudo-Done
fuehrt. Auch nicht skalierbar fuer neue Capabilities (Toleranzen,
STEP-Export, Constraint-Bemassung).

### Roadmap-Style (Q1/Q2/Q3 mit Datums-Targets)

Verworfen weil Datums-Targets in einem Forschungs-/Tooling-Projekt
unrealistisch sind und zu Druck fuehren statt zu Qualitaet. Capability×
Coverage ist Outcome-basiert statt Zeit-basiert.

### Reine Test-Pyramide (Unit/Integration/E2E)

Verworfen weil die heutigen Goldens-Layer (Splitter/Resolver/Pipeline)
keine klassische Test-Pyramide sind sondern Pipeline-Layer-Tests.
Coverage-Stufen 0-6 spiegeln das natuerliche Wachstum von Test-Robustheit
in DIESEM Projekt, nicht eine generische Hierarchie.

## Konsequenzen

### Vorteile

- **Single Source of Truth** fuer Projekt-Status: Capability×Coverage
  Matrix in CLAUDE.md.
- **"Fertig" wird ehrlich** — Capability X done = Cov 4 grün, nicht
  "Code ist da". Verhindert Pseudo-Done-Stempel.
- **Konsequente DIN-Integration** — jede neue Capability beginnt mit
  einer Konvention-Doc bevor Code geschrieben wird.
- **Skaliert** fuer neue Capabilities (additiv erweiterbar).
- **Klar fuer neue Mitarbeiter / spaetere Sessions** wo Mehrwert liegt
  und was als naechstes drankommt.

### Nachteile / Mehraufwand

- **Foundation-Aufwand** (1 Tag): CLAUDE.md restruct, conventions/
  Skeleton, ADR-Schreiben, Makefile-Tooling. Lohnt sich ab dem ersten
  Re-Plan-Anlass.
- **Coverage-Goldens schreiben braucht Disziplin** — pro Capability ein
  L2-Coverage-Golden mit ~10-20 Varianten ist Arbeit. Aber jede Stunde
  hier spart 5 Stunden Bug-Hunting in 3 Monaten.
- **Done-Review-Checkliste** ist 17 Punkte. Ohne Disziplin wird sie
  uebersprungen. Wir nutzen sie konsequent — sonst macht sie keinen Sinn.

### Auswirkung auf bestehende Dokumente

- **CLAUDE.md** Phase 1-Sektion + Future-Architecture-Sektion werden
  durch Capability-Matrix ersetzt. Stufenplan-Header bleibt als
  High-Level-Vision.
- **Memory `project_next_phase_plan.md`** wird komplett neu geschrieben
  mit der Matrix als Referenz.
- **Memory `project_phase_1_abschluss.md`** wird als historisch markiert.
- **Memory `project_golden_set_plan.md`** bleibt als historisches Dokument
  zur Stufenplan-Vision.
- **`docs/conventions/`** wird neu angelegt als DIN/ISO-Konvention-
  Bibliothek. Index in `docs/conventions/README.md`, pro Capability
  eine Datei.
- **`Makefile`** + `pyproject.toml` werden um Quality-Gates erweitert
  (ruff, mypy, radon, vulture).

## Stand bei Annahme dieses ADR

Capability 1.0 Primitive Assembly ist auf **Cov 3** (alle 18
Component-Goldens grün, einschliesslich V2_balanced_feature_palette).
Cov 4 fehlt noch (STRESS-Goldens mit ~20+ Features).

Alle anderen Capabilities sind auf Cov 0 oder teils gebaut ohne Goldens.
