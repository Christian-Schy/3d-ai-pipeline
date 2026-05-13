# ADR 0007 — Inventar Step A: Pro-Teil-Chunking fuer Multi-Part-Specs

- **Datum:** 2026-05-12
- **Status:** active (Plan, Implementierung folgt)
- **Vorgaenger-ADRs:** 0003 (Pro-Aktion-Mikro-Calls), 0006 (Klassifizierer-Split)
- **Verwandt:** Memory `project_split_pattern_candidates.md`

## Problem

Inventar Step A (`InventarAgent.extract_teile_only`) extrahiert die
Teil-Liste in **einem** LLM-Call ueber die ganze Spec. Bei langen
Multi-Part-Specs mit vielen gleichartigen Teilen verliert das 26b-Modell
den Faden:

- E_kombo (~13 Plates `80x40x20`): Inventar liefert **11 statt 13 Teile**
  und halluziniert mittendrin einen Param-Key
  (`platte_5: {'do_not_use_this_id_if_not_needed': 0, 'x': 80, ...}`).
- Heatmap-Fail (`data/sessions/heatmap_20260512_204022.md`):
  `E_kombo aktions_splitter feature-count: erwartet 13, bekommen 11` —
  Wurzel ist Step A, nicht der deterministische Splitter.

Es gibt heute einen `_extract_sequential`-Pfad mit Step A + Step B, aber
Step A selbst bleibt darin ein einzelner Call. Die Faktorisierung fehlt
genau dort wo sie noetig ist.

**Gleiche Klasse von Problem wie Klassifizierer-Monolith und Platzierer-
Monolith vor ihren Splits:** ein zu breiter Single-LLM-Call. Loesung
nach demselben Prinzip — zerlegen, deterministisch aggregieren.

## Entscheidung

**Pro-Teil-Chunking fuer Step A**, additiv mit Fallback auf den heutigen
One-Shot:

1. Neuer deterministischer **Teil-Deklarations-Splitter**
   (`src/tools/teil_splitter.py`) — segmentiert die Spec an klaren
   Grenzen in Teil-Deklarations-Phrasen. Eine Deklaration beginnt mit
   `<size>mm <teil>` oder `<seite> soll eine? <teil> <dims>` o.ae.
   Fragmente die keine neue Deklaration starten (Orientierung, Anker,
   Placement) werden an die vorherige Deklaration angehaengt — **nie
   mitten in einer Info abschneiden** (Lehre aus B3 v1 / Splitter-
   Param-Continuation).
2. Neue Methode **`InventarAgent.extract_teile_chunked(spec)`**:
   - Splitter liefert Deklarations-Phrasen
   - `<= N` Deklarationen (z.B. N=4): faellt auf `extract_teile_only`
     One-Shot zurueck (kein Overhead fuer den Normalfall)
   - `> N`: pro Deklaration (oder Batch von 2-3) ein fokussierter
     Step-A-Mikro-Call ("hier eine Teil-Deklaration: was ist das Teil?")
   - Deterministische Aggregation: Teile sammeln, **IDs durchnummerieren**
     (`platte_1`, `platte_2`, ... — Eindeutigkeit ueber Chunks hinweg),
     Param-Halluzinationen (unbekannte Keys) deterministisch filtern
3. `inventar_node`: bei `_is_complex` (oder eigenem Multi-Part-Threshold)
   `extract_teile_chunked` statt `extract_teile_only`.

## Konsequenzen

### Vorteile

- **Lineare statt monolithische Skalierung** — 13 Plates, 50 Plates,
  egal: jeder Mikro-Call sieht nur eine Deklaration. Skaliert fuer
  Stufe 4 (mehrteilige bewegliche Teile, grosse Assemblies).
- **Keine Param-Halluzinationen** — ein Mikro-Call der eine
  `80x40x20`-Deklaration sieht kann keinen `do_not_use_this_id`-Key
  erfinden; der deterministische Aggregator filtert ohnehin unbekannte
  Keys.
- **Deterministisches Counting** — die Anzahl Teile ist die Anzahl
  Deklarations-Phrasen, nicht das was das LLM zufaellig zaehlt.
- **Additiv + Fallback** — One-Shot bleibt fuer einfache Specs;
  bei Splitter-Versagen (0 Deklarationen) faellt es auf One-Shot zurueck.
- **Konsistent mit ADR 0003** — das ist der Pro-Teil-Split fuer Step A,
  Gegenstueck zum Pro-Aktion-Split fuer Step B.

### Risiken & Gegenmittel

- **Splitter erkennt eine Deklaration nicht** → faellt in den vorherigen
  Chunk → ein Teil zu wenig. Gegenmittel: Splitter konservativ, breite
  Deklarations-Muster; bei `0` erkannten Deklarationen voller One-Shot-
  Fallback.
- **Splitter schneidet mitten in einer Deklaration** → Teil mit
  unvollstaendigen Dims. Gegenmittel: nur an klaren Grenzen splitten
  (neue Deklaration beginnt), Continuation-Fragmente anhaengen — exakt
  das Muster von `aktions_splitter._is_param_continuation`.
- **ID-Kollisionen ueber Chunks** → deterministisches Durchnummerieren
  beim Mergen (`<typ>_1`, `<typ>_2`, ...). Downstream-Code (aggregator,
  platzierer) referenziert teil_id stabil — Renumbering passiert VOR
  allem Downstream.
- **Mehr LLM-Calls** → nur bei komplexen Specs (Threshold), und jeder
  Call ist winzig (eine Deklaration). Latenz-Netto unklar bis gemessen;
  Korrektheit hat Vorrang.

### Verworfen

- **Nur Count-Hint in den One-Shot-Prompt** ("es gibt N Plates") — hilft
  beim Counting, aber das LLM kann immer noch mid-generation den Faden
  verlieren und halluzinieren. Pflaster, kein Strukturfix.
- **Deterministische Teil-Extraktion komplett** (Regex parst Dims) —
  funktioniert fuer `80x40x20`-Standardformen, aber bricht bei
  Vokabular-Erweiterungen (Konturen, Revolve-Profile). Determinismus als
  Pflaster fuer Textverstehen, CLAUDE.md-Antipattern.

## Umsetzung

**Phase A — Teil-Splitter (deterministisch, keine Runtime-Aenderung)**

1. `src/tools/teil_splitter.py`: `split_spec_into_teil_declarations(spec)
   -> list[str]`. Regex fuer Deklarations-Start (`<size>mm <teil>`,
   `<seite> soll ... <teil> <dims>`, `<teil> <dims>` am Segment-Anfang),
   Continuation-Anhaengen fuer Nicht-Deklarations-Fragmente.
2. Unit-Tests: E_kombo-Spec → 13 Deklarationen; B*-Specs (single-part) →
   1 Deklaration; Continuation-Faelle ("die 80x40 seite liegt auf" haengt
   an); Cross-Teil-Schutz.

**Phase B — `extract_teile_chunked` (additiv)**

3. Neue Methode in `InventarAgent`. Threshold `N` (Start: 4 Deklarationen
   ODER Spec > 350 Zeichen + Multi-Part-Hints — gleicher `_is_complex`).
4. Pro Deklaration: Step-A-Mikro-Call (gleicher `TEILE_LISTE_SYSTEM`/
   `TEILE_LISTE_TEMPLATE`, aber Input = die eine Deklaration). Robust
   gegen Listen-vs-Dict-Response wie der bestehende Code.
5. Aggregator: dedupe (gleiche Dims + gleiche beschreibung = ein Teil?
   nein — jede Deklaration ist ein eigenes Teil, auch bei gleichen Dims),
   ID-Renumbering, Param-Key-Whitelist (`x`, `y`, `z`, `r`, `h`, ...),
   `type` default `box`.

**Phase C — Wiring + Verifikation**

6. `inventar_node`: `extract_teile_chunked` bei `_is_complex`.
7. Heatmap-Diff: E_kombo erwartet PASS (13 Teile). Andere Specs
   unveraendert (single-part → One-Shot-Fallback).
8. Bei gruen: Memory + CHANGELOG.

## Erfolgsmessung

- E_kombo: 13 Teile, kein halluzinierter Param-Key, Heatmap PASS.
- Andere 16 Specs: unveraendert (One-Shot-Pfad fuer single-part).
- Gesamtziel: Heatmap 16/1 oder 17/0 (zusammen mit M_kombo-Fix).
- Sekundaer: ein synthetischer 30-Plate-Spec produziert 30 Teile ohne
  Halluzination (Skalierungs-Smoke-Test).

## Was danach im gleichen Prinzip folgt

- **Step B Pro-Aktion** ist bereits umgesetzt (aktions_splitter +
  aktions_klassifizierer + feature_definierer + aggregator, ADR 0003).
- **Multi-Assembler** (Phase 3) routet pro `feature.type` an
  MergeAssembler / JoinAssembler / ContourAssembler / RevolveAssembler —
  das ist der naechste Split auf der Bau-Seite, aber erst wenn komplexe
  Formen dran sind.
- **Validator-Kette** (Phase B / Punkt-6) — pro-Aspekt-Validatoren +
  deterministische Geometry Assertions. Verifikations-Seite, separater
  Block.
