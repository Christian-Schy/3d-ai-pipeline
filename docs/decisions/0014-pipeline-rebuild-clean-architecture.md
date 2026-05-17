# ADR 0014 — Pipeline-Rebuild: Clean Per-Action Architecture

- **Datum:** 2026-05-17
- **Status:** proposed (Umbau-Plan — Implementierung als sequenzierte Workstreams)
- **Vorgaenger-ADRs:** 0003 (Pro-Aktion-Mikro-Calls), 0006 (Klassifizierer-Split),
  0009 (Pattern-Split), 0013 (Normalizer-Split — durch dieses ADR ueberholt)
- **Verwandt:** Memory `rebuild-plan-2026-05-17`, `pipeline-structure-audit-2026-05-17`,
  `feedback_determinism_scope`, `feedback_open_vs_closed_vocabulary`

> Dieses ADR ist der **Master-Plan fuer den Architektur-Umbau**. Es ersetzt
> ADR 0013 (Normalizer-Split): der Normalizer wird nicht gesplittet, sondern
> eliminiert. Jeder Workstream unten wird beim Umsetzen ggf. ein eigenes
> Detail-ADR bekommen.

## 1. Problem — die wiederkehrende Krankheit

Die Pipeline bricht bei jeder Erweiterung. Ursache ist **nicht** mangelnde
Funktion einzelner Teile, sondern ein systematisches Architektur-Muster:

> **Re-Derivation & Konventions-Fragmentierung:** Ein Agent leitet etwas neu
> ab, das ein anderer Agent schon wusste — oder eine Konvention lebt nur in
> einem von mehreren gleichrangigen Agenten.

Belege (Session 2026-05-17, alle per Trace bestaetigt):

| Fall | Re-Derivation / Fragmentierung |
|---|---|
| t08 / n04 | Normalizer re-parsed Positionierung blind, die der Klassifizierer schon hatte |
| V2 | Pattern-Klassifizierer *weiss* (per Keyword-Routing) dass es ein Grid ist, emittiert aber generisch `bohrung`; Normalizer raet die Familie neu → falsch |
| EF/NEST/N_kombo | Ecken-Regel lebt nur im `pocket_classifier`, fehlt in `hole_/slot_classifier` |
| Anker | Anker-Erkennung (Textverstaendnis) als Regex in `_infer_phrase_anchor` statt im LLM |

Folge: jede neue Capability (zuletzt Bohrungsmuster, ADR 0009) belastet einen
ohnehin ueberladenen Hand-off, und es gab kein schnelles per-Agent-Netz, das
den Drift fing. → Regressions-Kaskade, 10-facher Nacharbeits-Aufwand.

## 2. Entscheidung — sieben Architektur-Prinzipien

1. **Ein Textverstaendnis-Schritt pro Aktion.** Der typ-spezifische
   Klassifizierer ist der EINZIGE LLM, der die Aktions-Phrase liest. Er
   emittiert einen vollstaendigen, **spezifischen** Action-Descriptor
   (typ konkret, seite, alle Parameter, Positionierungs-Konvention,
   Rotation, Anker falls vorhanden).
2. **Keine Re-Derivation.** Was ein Agent produziert, fliesst downstream
   unveraendert. Alles nach dem Klassifizierer ist deterministisch.
3. **Normalizer wird eliminiert.** Seine Aufgaben wandern: typ-Verfeinerung
   → Klassifizierer emittiert spezifischen typ; Positionierung → schon
   Klassifizierer; richtung/Anker → Klassifizierer. Der deterministische
   `feature_builder` konsumiert den Klassifizierer-Output direkt.
   (Loest ADR 0013 ab — Split eines Agenten, der ganz verschwindet,
   waere Verschwendung.)
4. **Konventionen = geteilte Bibliothek.** Ein Modul definiert jede
   DIN-/Positionierungs-Konvention (Ecken-Regel, Rotation-Vorzeichen,
   "durch", buendig, edge-to-edge vs edge-to-center). Jeder Klassifizierer-
   Prompt inkludiert die relevanten Fragmente. Konvention aendern = eine
   Stelle, propagiert ueberall. Nie wieder Fragmentierung.
5. **Determinismus-Grenze strikt — Regex NIE auf User-Text.**
   LLM = offenes Vokabular (Textverstaendnis). Code = Mathe,
   geschlossenes-Vokabular-Mapping, Assembly.
   - ERLAUBT: Regex/Parsing auf bereits STRUKTURIERTEM Output (z.B. den
     Achsen-Token `x` aus der LLM-Antwort lesen).
   - VERBOTEN: Regex auf die rohe User-Phrase. Formulierungs-Varianten
     und Fehlformulierungen sprengen jedes Muster — genau das ist die
     Schwachstelle. Betrifft nicht nur `_infer_phrase_anchor`, sondern
     AUCH das Keyword-Routing der Sub-Klassifizierer
     (`detect_classifier_subagent`) und die Normalizer-Regex-Helfer
     (`_corner_point_from_text`, `_infer_direction_from_phrase`, ...).
   Alle in W5 inventarisieren → LLM-Entscheidung oder loeschen.
6. **Per-Agent-Regression-Suite ist Pflicht.** Jeder LLM-Agent hat eine
   schnelle kuratierte Suite (`tests/agent_regression/`, Marker
   `agent_regression`, ~1 min/Agent). `make retrain-validate A=<agent>`
   ist die EINZIGE Trainings-Operation. Kein Training ohne Suite-Gate.
7. **Per-Aktion-Uniformitaet = Skalierbarkeit.** 1 Feature oder 20, jede
   Komplexitaet: identischer per-Aktion-Pfad. Keine globalen Mega-Calls.
   Per-Aktion-Calls sind unabhaengig → parallelisierbar.

## 3. Ziel-Architektur

**Heute (fragil):**
```
... → aktions_klassifizierer (→ sub-classifiers, typ GENERISCH)
    → feature_definierer (→ NormalizerAgent: LLM RE-PARSED Rohtext)
    → _merge_param_hints (raeumt Konflikt zweier Parses auf)
    → feature_builder → aggregator → resolver → ...
```

**Ziel (ein LLM-Schritt pro Aktion, Rest deterministisch):**
```
... → aktions_splitter (rule)
    → typ-Klassifizierer (LLM, EINZIGER Textverstaendnis-Schritt):
        vollstaendiger Action-Descriptor, spezifischer typ
    → feature_builder (rule): Descriptor → SemanticFeature
    → aktions_aggregator (rule) → platzierer → resolver → ...
```

Der `NormalizerAgent` und `_merge_param_hints` entfallen. Der Dual-Parse-
Bug-Klasse ist damit strukturell unmoeglich.

## 4. Blueprint-Schema v3 — Positionierung konsolidieren

Heute wird Positionierung auf **vier** Arten ausgedrueckt: `edge_distances`,
`center_offset`, `pocket_edge_distances`, `anchor`. Diese Mehrfach-
Repraesentation ist ein Hauptgrund fuer chaotische Merges.

v3: EIN `placement`-Objekt mit `convention`-Tag (`edge_to_center` |
`edge_to_edge` | `center_offset` | `anchor`) + Werten. Migration additiv
(neues Feld, alte bleiben lesbar bis alle Pfade umgestellt sind). Schema
war eingefroren — dieser Umbau ist die begruendete Ausnahme.

## 5. Test-Struktur — die Fehleranalyse-Pyramide

| Layer | Was | Dauer | Faengt |
|---|---|---|---|
| L0 Unit | Parsing, Format, Determinismus-Funktionen | ms | Code-Bugs |
| L0.5 Agent-Regression | je LLM-Agent kuratierte Cases gegen Ollama | ~1 min/Agent | Prompt-/Demo-Drift, Agent-Wobble |
| L1 Component-Goldens | Resolver/feature_builder isoliert, deterministisch | s | Determinismus-Bugs |
| L2 Pipeline-Heatmap | Voll-Integration, alle Specs | ~25 min | Integrations-/Komposition-Bugs |

Jeder Fail mappt eindeutig auf einen Layer → man weiss sofort WO. L0.5 ist
das neue, in dieser Session gebaute Netz und der Kern der Praevention.
**Luecke heute:** kein schnelles Integrations-Signal zwischen L0.5 und L2 →
Workstream W7 (Mini-Heatmap ~5 Specs).

## 6. Vorgegriffene Probleme (praeventiv)

Aus dem Grundmuster abgeleitet — wird im Umbau direkt mit-adressiert:

- **Konventions-Fragmentierung** (Rotation-Vorzeichen, "durch", buendig):
  → Workstream W2 (Konventions-Bibliothek) loest es generell.
- **Regex-Landminen** in `normalizer_agent.py` (`_corner_point_from_text`,
  `_infer_direction_from_phrase`, `_CHILD_CORNER_RE`, ...): → W4/W5
  loeschen sie mit dem Normalizer.
- **Demo-Wander** (DSPy waehlt 8–16 von N): → W6 KNNFewShot, alle Demos
  zur Inferenzzeit retrievebar.
- **Kein Integrations-Frueh-Signal:** → W7 Mini-Heatmap.
- **Neue Capability destabilisiert Bestehendes:** → strukturell verhindert,
  weil neue Feature-Typen rein additiv sind (neuer Klassifizierer + neue
  Konventions-Fragmente, kein Eingriff in bestehende Agenten).

## 7. Workstreams (sequenziert, jeder Suite-/Heatmap-gegated)

| WS | Inhalt | Vorbedingung |
|---|---|---|
| W1 | Agent-Regression-Suiten fuer ALLE LLM-Agenten (hole, slot, grid, circular, linear, edge_feature, interpreter, inventar, position_extractor, platzierer×4). **Zugleich Entdeckungs-Instrument** fuer Re-Derivation im Front-/Placement-Layer (siehe §10). | — |
| W2 | Konventions-Bibliothek (`data/prompts/conventions/`) + jeder Klassifizierer macht VOLL-Extraktion (Ecken-Regel etc. ueberall) | W1 |
| W3 | Pattern-Klassifizierer emittieren spezifischen typ; Normalizer-typ-Verfeinerung raus | W1, W2 |
| W4 | Normalizer-Elimination: Klassifizierer → `feature_builder` direkt; `_merge_param_hints` weg | W1–W3 |
| W5 | Regex-auf-User-Text-Audit: JEDE Regex die die rohe Phrase liest (Anker-Helfer, Klassifizierer-Keyword-Routing, Normalizer-Helfer) inventarisieren → LLM-Entscheidung oder loeschen. Anker-Erkennung in den Klassifizierer. | W4 |
| W6 | `KNNFewShot` statt `BootstrapFewShot` evaluieren + umstellen | W1 |
| W7 | Mini-Heatmap (~5 repraesentative Specs) als schnelles Integrations-Signal | — |
| W8 | Blueprint-Schema v3 (Positionierung konsolidieren) | W4 |
| W9 | CLAUDE.md + `docs/` auf neue Architektur umschreiben | W4–W8, W10 |
| W10 | **Modifikations-/Error-Loop-Pfad vereinheitlichen.** Heute laeuft er ueber die ALTE Agent-Kette (blueprint_architect/coder) — eine komplette zweite Pipeline (Memory `project_modification_uses_old_chain`). Auf die neue Per-Aktion-Architektur umstellen, alte Kette loeschen. Re-Derivation auf Pipeline-Ebene. | W4 |

**Migrations-Disziplin pro WS:** hinter Flag, L0.5-Suite gruen, L2-Heatmap
bestaetigt, dann erst naechster WS. Die gruene Baseline wird nie gebrochen.

## 8. Bereits begonnen (Session 2026-05-17)

Teile von W1/W2/W4 sind angefangen und im Working Tree (uncommitted):
- L0.5-Infrastruktur: `tests/agent_regression/` + Marker + `make
  retrain-validate` — **das Fundament des ganzen Plans**.
- pocket_classifier 16/16, normalizer 16/16 Agent-Regression gruen.
- `_merge_param_hints` autoritativ (Zwischenschritt — entfaellt mit W4).
- Normalizer teil-spezialisiert (Positionierung raus) — Zwischenschritt
  Richtung W4.
- pocket-Ecken-Regel — wandert in W2 in die Konventions-Bibliothek.

Der neue Chat startet bei W1 (Suiten vervollstaendigen) und faltet die
Zwischenschritte in die Ziel-Architektur.

## 9. Konsequenzen

- **Positiv:** Dual-Parse-Bug-Klasse strukturell unmoeglich. Neue
  Capabilities additiv. Skaliert per-Aktion. Jeder Fehler hat einen
  eindeutigen Layer + Agenten. Training reproduzierbar + Suite-gegated.
- **Kosten:** mehrwoechiger Umbau, sequenziert. Schema-v3-Migration.
- **Risiko:** beherrscht durch WS-Sequenzierung + Suite-Gates — jeder
  Schritt ist einzeln verifiziert, die Baseline bleibt gruen.

## 10. Offene Audit-Felder — ehrlich ueber die Grenzen des Plans

Dieses ADR adressiert die **diagnostizierte** Krankheit im Kern
Klassifizierer→Normalizer→feature_builder — dort liegt die Trace-Evidenz
dieser Session. Drei Felder sind NICHT verifiziert und muessen im Umbau
mit-auditiert werden. W1 (Suiten fuer alle Agenten) ist das
Entdeckungs-Instrument dafuer:

1. **Front-Layer** (interpreter, inventar, aktions_splitter): nicht auf
   Re-Derivation geprueft. `inventar` war historisch ein
   Mega-Call-Bottleneck (70–313 s). Prinzip 1–2 + W1-Suiten gelten hier
   genauso.
2. **Placement-Layer** (position_extractor, platzierer×4,
   pocket_child_placer): ungeprueft, ob der platzierer etwas
   re-ableitet, das position_extractor schon hatte.
3. **Modifikations-/Error-Pfad** (W10): laeuft heute ueber eine komplett
   SEPARATE alte Agent-Kette — Re-Derivation auf Pipeline-Ebene, die
   groesste Doppelung im System.

Was dieser Plan **nicht** verspricht: „null zukuenftige Probleme" — das
kann kein Plan. Was er **garantiert**: die Bug-KLASSE Re-Derivation wird
strukturell unmoeglich; neue Feature-Typen sind rein additiv; und das
L0.5-Netz macht jeden neuen Drift in Sekunden sichtbar und lokalisiert
ihn auf genau einen Agenten. Probleme kaskadieren nicht mehr — das ist
der eigentliche Gewinn.

## 11. Verworfen

- **Normalizer splitten (ADR 0013):** einen Agenten splitten, der ganz
  entfallen kann, ist Verschwendung. ADR 0013 zurueckgezogen.
- **Weiter per Prompt-/Regex-Patch flicken:** erzeugt genau die
  Kaskade, die dieses ADR beendet.
