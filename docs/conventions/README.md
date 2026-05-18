# DIN/ISO Konventions-Bibliothek

Diese Bibliothek dokumentiert wie die Pipeline Konstrukteur-Wording nach
DIN/ISO interpretiert. Sie ist die **Single Source of Truth** fuer
Bemassungs- und Konstruktions-Konventionen.

## Wozu

Verkaufsziel ist B2B Maschinenbau-CNC-Konstrukteur (siehe CLAUDE.md
"Verkaufsziel"). Daraus folgt: Eingaben muessen so interpretiert werden
wie ein Konstrukteur sie nach DIN-Norm meint, nicht wie ein
Hobby-Programmierer raten wuerde.

Jede neue Capability (siehe CLAUDE.md Capability-Matrix) beginnt mit
einem Eintrag hier — bevor Code geschrieben wird. Das verhindert
nachtraegliche "ach so meinte das der User"-Patches.

## Was diese Bibliothek NICHT ist

Sie ersetzt **kein** LLM-Textverstaendnis durch deterministische Regeln.
Das Projekt bleibt ein KI-Projekt mit der Aufgaben-Trennung aus
CLAUDE.md "Entwicklungs-Prinzipien":

- **LLM:** Text → Bedeutung. Mehrdeutige Phrasen interpretieren,
  Konstrukteur-Sprache verstehen, Aktionen identifizieren, Anker-
  Vokabular auswerten.
- **Deterministisch:** Bedeutung → Geometrie. Koordinaten-Mathe,
  Face-Auswahl, Rotation, Dim-Swap, Code-Generierung aus Schema,
  Assembly via Resolver.
- **Coder (LLM Codegen):** komplexe Geometrien (Loft/Sweep/Spline)
  die nicht templatebar sind. Hier braucht es freien CadQuery-Code.

Die Konventions-Bibliothek hilft beiden Seiten:

1. **LLM-Seite:** Demos in `data/dspy_training/` orientieren sich an
   den hier dokumentierten Konventionen. Klassifizierer/Normalizer-
   Prompts referenzieren die Wording-Beispiele. Das LLM lernt
   konsistent dieselbe Konvention zu erkennen.
2. **Deterministische Seite:** Resolver/Templates/Aggregator
   implementieren die hier dokumentierten Mathe-Regeln. Bei
   geometrischen Mehrdeutigkeiten (z.B. Slot-Length-Achse) gewinnt
   die DIN-Konvention.

Wenn ein LLM-Call patzt: zuerst Demos/Prompt verbessern (Textverstaendnis-
Problem). Erst wenn das nicht reicht: deterministischen Schutz im
Resolver einziehen (Mathe-Korrektur, kein Pflaster fuer schlechtes
Textverstaendnis).

## Aufbau

Pro Capability eine Datei. Jede Datei enthaelt:

1. **Konvention** — die DIN/ISO-Regel kurz und konkret
2. **Wording-Beispiele** — typische User-Phrasen + erwartete Interpretation
3. **Edge-Cases** — bekannte Mehrdeutigkeiten + wie wir sie aufloesen
4. **Code-Pfad** — wo im Repo die Konvention implementiert ist (Resolver,
   Klassifizierer-Prompt, Templates)
5. **Tests** — welche Goldens / Unit-Tests die Konvention absichern
6. **Referenzen** — DIN/ISO-Dokumente, Norm-Nummern

## Verzeichnis

| Nr. | Capability | Status |
|---|---|---|
| [10](10_masseintragung_din406.md) | Masseintragung allgemein (DIN 406, ISO 129) | aktiv |
| [11](11_coverage_matrix.md) | Coverage-Matrix (Test-Aufbau pro Feature) | aktiv |
| [20](20_bohrung_din.md) | Bohrung (point-like, Matrix-abgeleitet) | aktiv (Pilot) |
| [21](21_nut_slot_din.md) | Nut/Slot-Bemassung (Length-Achse vs Width-Achse) | aktiv |
| [22](22_tasche_din.md) | Tasche/Pocket-Bemassung | aktiv (Coverage-Matrix-abgeleitet) |
| 23 | Polygon + Extended Primitives | TBD (Capability 1.5) |
| [24](24_pattern_din.md) | Pattern (Grid/Kreis/Linear-Reihe) | aktiv (Coverage-Matrix-abgeleitet) |
| [25](25_plate_din.md) | Plate-Assembly (Stack/Side/Auflage-Face) | aktiv (Coverage-Matrix-abgeleitet) |
| [26](26_edge_features_din.md) | Edge Features (Fase / Rundung — DIN 6784 / ISO 13715) | aktiv (Coverage-Matrix-abgeleitet) |
| 30 | Toleranzen ISO 286 (IT-Klassen, H7/g6) | TBD |
| 31 | GD&T ISO 1101 (Form-/Lagetoleranzen) | TBD |
| 40 | Norm-Bauteile DIN (Schrauben, Lager, Stifte) | TBD |
| 50 | Constraint-Bemassung (Symmetrie, Auto-Close, Feature-Bezuege) | TBD |
| 60 | STEP-Export-Konvention (AP242) | TBD |
| 90 | User-Wording-Beispiele (gesammelt aus echten Eingaben) | TBD |
| [98](98_engineering_plan.md) | Engineering-Capabilities-Plan (Roadmap Cap 1.5-8.0) | aktiv |
| [99](99_normen_audit.md) | Normen-Audit und Pipeline-Luecken | aktiv |

## Workflow fuer neue Eintraege

1. Neue Datei `<NN>_<thema>.md` anlegen mit den 6 Sektionen oben.
2. Eintrag in obige Tabelle ergaenzen.
3. Im Code-Kommentar (Resolver/Klassifizierer/Template) auf den Konvention-
   Eintrag verweisen mit Pfad: `siehe docs/conventions/NN_thema.md`.
4. Bei Aenderungen: Wording-Beispiele und Edge-Cases ergaenzen, NICHT
   Konvention rueckwirkend aendern (das ist Schema-Bruch).

## Ausnahmen

Wenn die Pipeline absichtlich von der DIN-Konvention abweicht, MUSS das
in der Datei begruendet werden — typisch weil eine Konvention im LLM-
Pipeline-Setting nicht praktikabel ist. Beispiel-Begruendung:
"DIN 406 erlaubt Centerline-zu-Edge fuer Slot-Width — wir nehmen
edge-to-Center, weil Konstrukteur-Wording 'von linker Kante 12mm' bei
schmalen Slots (≤3 mm Breite) ohnehin auf das Gleiche herauskommt und
das LLM-Wording-Spektrum kleiner wird."
