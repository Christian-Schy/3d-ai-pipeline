# ADR 0016 — Reverse-Validator-Rebuild Phasenplan

- **Datum:** 2026-05-18
- **Status:** planned (deferred, Trigger siehe unten)
- **Verwandt:** ADR 0015 (Dormanter Reverse-Validator-Pfad), ADR 0014
  (Pipeline-Rebuild Clean Architecture)

## Kontext

ADR 0015 hat das dormante Scaffold in `src/validation/` etabliert
(Contracts, Fact-Extraction, Coordinator, 6 Check-Module). Heute liefern
die BBox-/Volumen-/FeatureCount-Checks echte Ergebnisse; die Family-Checks
(Hole/Slot/Pocket) emittieren konservativ `unknown`, weil eine echte
Ist-Geometrie-Extraktion aus dem erzeugten STL/Body noch fehlt. Das
Scaffold ist **nicht** in `src/graph/pipeline.py` verdrahtet.

Der aktive Validator-Pfad (`plan_validator` + finaler `ValidatorAgent`)
bleibt LLM-lastig und ist bekanntermassen unzuverlaessig (CLAUDE.md
"Bekannte Limitierungen"). Parallel laufen deterministische Checks im
`coordinate_validator` (Slot-Restwandstaerke Check 11, rotations-bewusste
Pocket-AABB seit 2026-05-18) — die nehmen Last vom LLM-Pfad, sind aber
*Forward*-Checks (Blueprint-Konsistenz), kein echtes *Reverse* (Ist-
Geometrie ↔ Soll-Geometrie).

Der vollstaendige Reverse-Validator soll Spiegelbild der Bau-Kette werden:
viele kleine Experten von HINTEN nach VORNE, anderes Modell als Bau-Pfad
fuer unabhaengige Sicht, jeder prueft EIN Aspekt (Position, Drehung,
Flaeche, Anker, Feature-Count). Determinismus wo moeglich, LLM nur fuer
Textverstaendnis-Pruefung.

## Trigger / Vorbedingungen

Wann den Vollausbau starten:

1. **Cap 1.0 Cov 4 erreicht** — Build-Pipeline muss stabil sein, sonst
   validiert man instabile Outputs. Heute Cap 1.0 Cov 3 (18/18 Component-
   Goldens) + saubere Slot-Mittellinien-Migration; Cov 4 STRESS-Goldens
   stehen noch aus.
2. **Cap 6.0 (Datums) gestartet** — ohne Datum-Bezugssysteme kann der
   Reverse-Validator keine sinnvolle Positions-Pruefung gegen ein
   Bezugssystem machen.
3. **Cap 7.0 (Toleranzen + GD&T) konkretisiert** — der eigentliche
   Mehrwert des Reverse-Validators entsteht bei toleranzbehafteten
   Bezuegen (Positionstoleranz gegen Datum, Form-/Lage-Toleranzen). Ohne
   Toleranzen pruefen waere wie GD&T ohne Datum: leeres Geruest.

Heisst: **Start frühestens nach Cap 1.0 Cov 4 + parallel zu Cap 6.0
Vorbereitung**. Bis dahin bleibt das Scaffold dormant; deterministische
Checks im `coordinate_validator` werden weiter ausgebaut und sind spaeter
ins Reverse-Scaffold migrierbar.

## Phasenplan

Geplant als 5 Phasen, jeweils eine eigene Session. Phasen sind in
Reihenfolge abhaengig; Tests/Goldens pro Phase Pflicht.

### Phase 1 — STL-Feature-Geometry-Extraction

**Ziel:** Aus dem erzeugten CadQuery-Body bzw. STL die konkreten Feature-
Geometrien zurueckgewinnen — nicht nur Volumen/BBox.

- Bohrungen: Mittelpunkte + Durchmesser + Tiefe aus zylindrischen Faces.
- Slots: Endpunkt-Mittelpunkte + Mittellinie + Width aus Slot-Aussen-
  kontur.
- Taschen: 4 Aussenkanten + Tiefe + Rotation aus rechteckigen Faces.
- Pattern: Aufzaehlung der Kind-Features.

Code: neuer Modul `src/validation/stl_extraction.py` oder Erweiterung
`fact_extraction.py`. Nutzt CadQuery/OCCT-Face-Enumeration auf dem
Body (vor STL-Tessellation). Liefert strukturierte `ActualFeatureFact`-
Objekte parallel zu den blueprint-basierten `FeatureFact`.

**Tests:** Component-Goldens mit bekannten Geometrien (statisch erzeugte
STLs / Bodies); Vergleich extraktion vs. Erwartung per Feature-Typ.

### Phase 2 — Deterministische Feature-Drift-Checks

**Ziel:** Pro Feature den Drift Soll (Blueprint) ↔ Ist (Extraktion)
quantifizieren.

- `HolePositionDriftCheck` — Bohrungs-Mittelpunkt-Distanz Soll/Ist.
- `HoleDiameterCheck` — Durchmesser-Differenz.
- `SlotPositionDriftCheck` — Mittellinien-Distanz Soll/Ist.
- `SlotOrientationCheck` — Winkel-Differenz.
- `PocketBoundsCheck` — 4-Kanten-Position + Rotation.
- `PatternMemberCheck` — jede Kind-Bohrung des Patterns auffindbar.
- `FeatureCountConsistencyCheck` — Anzahl Features Ist == Soll.

Toleranzen pro Check konfigurierbar (Default: 0.1mm Position, 0.5°
Winkel; spaeter aus Toleranz-Schema in Cap 7.0).

Code: neue Check-Klassen in `src/validation/checks/`. Setzen den
`unknown`-Status der heutigen Family-Checks auf `passed`/`failed`/
`unknown` basierend auf der Extraktion aus Phase 1.

**Tests:** Per Check Unit-Tests mit Mock-Facts. L0.5-Goldens mit
Blueprint+Mock-STL-Paaren.

### Phase 3 — Spezial-LLM-Agenten fuer Text-vs-Geometrie

**Ziel:** Die Aspekte, die deterministisch nicht entscheidbar sind —
"hat die User-Phrase tatsaechlich diese Geometrie gemeint?".

Mirror von ADR 0014 Klassifizierer-Sub-Agents, nur fuer den Reverse-Pfad
und mit anderem Modell als der Build-Pfad (unabhaengige Sicht). Pro
Aspekt ein Agent:

- `ReverseAnchorValidator` — passt der extrahierte Anker zur User-Phrase?
- `ReversePositionValidator` — passt die extrahierte Position zur
  beschriebenen Lage?
- `ReverseRotationValidator` — passt der Winkel zur "X° gedreht"-
  Phrase?
- `ReverseFeatureCountValidator` — wurde alles erkannt was im User-Text
  erwaehnt war?

Modell-Wahl: **anderes** Modell als der Klassifizierer im Build-Pfad,
um Korrelations-Bias zu vermeiden (z.B. Build = gemma4:26b → Reverse =
qwen3.5:30b o.aehnlich).

Klare Aufgaben-Trennung: kein Regex auf User-Text, kein Mathe (das
machen Phase-2-Checks). Jeder Agent kriegt strukturierte Facts +
Phrase, antwortet ja/nein/unklar mit Begruendung.

**Tests:** L0.5-Style Agent-Regression-Suiten pro Validator-Sub-Agent
(`tests/agent_regression/test_reverse_*_validator.py`), 16+ Cases je.

### Phase 4 — Pipeline-Verdrahtung (non-blocking → blocking)

**Ziel:** Reverse-Validator nach dem aktiven Validator einhaengen,
zunaechst als Cross-Check ohne Blockade.

- `src/graph/pipeline.py`: neuer Node `reverse_validator_node` nach
  `validator_node`.
- `GRAPH_INTEGRATION_ENABLED = True` (ADR 0015).
- Erste Periode: `BLOCKING_ENABLED = False` — Reverse-Report wird
  gelogged, aber blockiert den Run nicht.
- Heatmap-Auswertung: gibt der Reverse-Validator stabile Ergebnisse?
- Sobald Stabilitaet bewiesen: `BLOCKING_ENABLED = True` — Reverse-Fail
  triggert Error-Loop (mit Reverse-Befund als Feedback an den Code-
  Fixer).

**Tests:** Pipeline-Integration-Smoke-Tests mit Mock-Reverse-Reports.

### Phase 5 — Per-Agent-Regression-Suite Vollstaendigkeit

**Ziel:** Wie der Build-Pfad eine L0.5-Suite hat (ADR 0014 W1, 83 Cases),
hat auch der Reverse-Pfad eine — als Drift-Detection-Netz.

- Pro Reverse-Sub-Agent eine kuratierte Test-Liste (16+ Cases) mit
  bekannten Soll/Ist-Geometrien.
- `make agent-regression` laeuft beide Suiten.
- `make retrain-validate A=<reverse_agent>` mirror der Build-Pfad-
  Retrain-Loop.

**Tests:** Suite ist der Test.

## Konsequenzen

**Positiv:**
- Unabhaengiger Cross-Check entlastet den LLM-`ValidatorAgent`.
- Fakten + Evidenz statt Pass/Fail-Black-Box.
- Spaetes Erkennen von "Pipeline laeuft, aber STL stimmt nicht zur Spec".
- Voraussetzung fuer GD&T-Validation (Cap 7.0).

**Negativ / Kosten:**
- Mehrere Sessions Aufwand (3–5).
- Mehr LLM-Calls pro Pipeline-Run (~+30–60% Latenz wenn Spezial-
  Agenten eingehaengt sind).
- Modell-Wahl: zweites Modell muss im VRAM landen koennen oder seriell
  geladen werden (`num_ctx`-Mismatch-Risiko, vgl. Memory `num_ctx`-
  Erkenntnis).

**Migrations-Pfad fuer bestehende deterministische Checks:**
- `coordinate_validator.py` Check 11 (Slot-Restwandstaerke), die
  rotations-bewusste Pocket-AABB und ein zukuenftiger Pattern-Kind-
  Check sind **Forward-Checks** (Konsistenz innerhalb des Blueprints).
- Sie bleiben aktiv im Forward-Pfad. Die **Reverse**-Pendants
  (Restwandstaerke aus *gemessener* STL-Geometrie, Pocket-Aussen-
  kontur aus *extrahierten* Faces) entstehen in Phase 2 und ergaenzen
  die Forward-Checks, ersetzen sie nicht.

## Verworfene Alternativen

- **Sofort starten:** Verworfen — Cap 6.0/7.0-Vorlauf fehlt; Reverse-
  Validator ohne Datum/Toleranzen waere ein leeres Geruest.
- **LLM-Validator weiter aufbohren:** Verworfen — die Ueberladung des
  einzelnen `ValidatorAgent` ist genau das Problem (siehe ADR 0014 fuer
  Build-Pfad-Begruendung; symmetrisch fuer Validator-Pfad).
- **Determ. Forward-Checks reichen:** Teilweise verworfen — Forward-
  Checks pruefen Blueprint-Konsistenz, nicht Soll-vs-Ist nach
  Code-Execution. Beide Pfade noetig.

## Stand

Plan-Doc neu (2026-05-18). Trigger-Vorbedingungen formuliert, Phasen
skizziert. Wird bei Trigger-Eintritt zu einem aktiven Workstream mit
eigenem Tracking; bis dahin steht das Scaffold (`src/validation/`)
unveraendert weiter.
