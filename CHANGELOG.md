# Changelog

Chronologische Liste nennenswerter Aenderungen am Projekt. Pro Eintrag der
Commit-Hash, eine Kurzbeschreibung und (wenn vorhanden) ein Verweis auf die
zugehoerige ADR unter `docs/decisions/`.

Architektur-Entscheidungen liegen als ADRs (Architecture Decision Records)
in `docs/decisions/` — dort steht das **Warum** zu jeder grundlegenden
Aenderung. Hier in der Changelog steht das **Was** mit Datum.

## 2026-05-15

- **Validator-Fix: asymmetrische Volumen-Toleranz fuer Multi-Part-Assemblies.**
  `_volume_check_passes` behandelte die naive Volumen-Summe (Wuerfel + alle
  Platten) als exakten Erwartungswert mit symmetrischer ±20%-Toleranz. Bei
  Multi-Part-Assemblies mit ueberlappenden additiven Teilen (E_kombo: 12
  Platten "geometrisch ueberlappend") ist die Summe aber eine **Obergrenze**
  — Overlap reduziert das echte Union-Volumen. E_kombo lag mit 21.3% unter
  der Summe, knapp ueber der Schwelle → Volume-Check schlug fehl → LLM-
  Semantik-Check sprang an und las die 150×120×120-Bounding-Box faelschlich
  als "Wuerfel 120mm statt 100mm" → Validator-Retry-Schleife (~8 Min
  verschwendet, 2-3 Runden). Fix: bei >=2 additiven Solids (neuer Helper
  `_count_additive_solids`) gilt asymmetrische Toleranz — `actual <
  expected` ist normal (Overlap), nur `actual > expected*1.2` ist ein
  echter Fehler. E_kombo laeuft jetzt one-shot (290s statt 1100s, kein
  Retry). Single-Solid-Blueprints behalten die symmetrische Pruefung.

- **L2-Coverage-Pilot: `B_coverage_all_sides_all_wordings` (Bohrung).**
  Erstes von vier geplanten L2-Coverage-Goldens (CLAUDE.md "Capability 1.0
  → Cov 4"). Deckt H01-H06 + H08-H10 aus `docs/conventions/20_bohrung_din.md`
  ab — 9 Bohrungen auf einem Wuerfel 100x80x40 ueber alle 6 Seiten mit
  A1/A3/A4/A6 × B0-B3 × C0. Pipeline-Test PASS in 78s, voller Heatmap
  19/0 (B/T/N/M/E/EF/V2/NEST/M_kombo). Resolver-Math via einmaligem
  `resolve_blueprint` aus semantischem Input erzeugt.

- **Konventions-Korrektur 20 (Bohrung): A5 (Bauteil-Face-Anker) entfaellt
  fuer point-like Bohrung.** "In der oberen rechten Ecke 8mm nach links
  versetzt" ist mathematisch identisch zu A1 mit
  `abstand_rechts: 8`; eine Bohrung hat keine eigene Ecke. A5 gilt
  weiterhin fuer Plate (Konvention 25), Tasche (22) und Pattern (24) —
  also Features mit eigener Bounding-Box. H07 entfaellt aus Test-Liste
  (9 statt 10 Cases).

- **Pattern-A1-Konvention encoded: `hole_pattern_linear` mit
  `edge_distances` referenziert outermost-Hole.** Per Konvention
  [`docs/conventions/24_pattern_din.md`](docs/conventions/24_pattern_din.md)
  unterscheidet die Pattern-Bemassung jetzt nach Typ: Grid und Linear-Reihe
  beziehen `abstand_*` auf die **outermost-Hole** (DIN-konstrukteurnah),
  Kreis bleibt auf den Pattern-Center (Teilkreis-Bezugspunkt). Im Resolver
  rechnet `_get_child_face_size` fuer `hole_pattern_linear` jetzt den
  Pattern-Span `(count-1)*spacing` entlang der direction-Achse als
  Footprint zurueck, und `_compute_offsets` setzt fuer Linear das
  per-Achse `is_box_wx/wy`-Flag analog zu Slot — so subtrahiert die
  edge-Distance-Math den Pattern-Half auf der Richtungs-Achse, waehrend
  die perpendikulare Achse edge-to-center bleibt. Grid erbt die Konvention
  bereits aus dem `count + inset`-Template (inset IST die
  outermost-Hole-Distance). Kreis braucht keine Aenderung. Full Heatmap
  18/0 — V2_balanced_feature_palette ebenfalls geheilt (vorher 17/1).

## 2026-05-14

- **Platzierer-Stabilitaet: Anchor-Recognition + Merge-Logik-Fix.**
  Vier zusammengehoerige Aenderungen, die E_kombo_basics (Multi-Part mit
  Anker-Vokabular) von FAIL auf PASS bringen und keine anderen Goldens
  regressen (Full Heatmap 17/1):
  1. Anchor-Mini-Call feuert jetzt IMMER (Gate entfernt). Der Prompt
     erlaubt leere Ausgabe wenn kein echter Anker da ist, der LLM
     entscheidet via Demos. Loest das Labeler-Child-ID-Pattern
     ("obere kante der platte_7 auf obere kante des wuerfels"), bei dem
     der frueher gebrauchte Trigger-String-Match scheiterte.
  2. `prompt_position_alignment` mit explizitem ANKER-MUSTER-Block:
     "Wenn ein Kanten-/Ecken-Wort zweimal mit 'auf' dazwischen steht,
     ist es ANKER-Sprache — Alignment ist immer zentriert, nie buendig_*."
     Verhindert dass die LLM-Bias-Bindung "untere kante" -> "buendig_unten"
     ueber das spezifische Demo gewinnt.
  3. `prompt_position_anchor` mit explizitem Edge-on-Edge-Beispiel
     ("KIND-Kante auf PARENT-Kante ist ECHTER Anker, auch wenn es wie
     buendig klingt").
  4. `prompt_position_offset` mit "Pro Achse hoechstens eine Richtung"-
     Regel — verhindert geometrisch unmoegliche Doppelangaben
     (versatz_rechts=5 UND versatz_links=10).
  5. Merge-Logik in `position_normalizer_agent._merge` korrigiert:
     `zentriert` bleibt `zentriert` wenn ein reiner Point-on-Point Anker
     ohne Offset vorliegt. Vorher: jeder Anker mit `zentriert` wurde
     zwangsweise auf `von_kanten` geflippt, auch wenn `abstand={}` leer
     war. Konsequenz: Adapter `_adapter_platzierer_alignment` muss nicht
     mehr auf den Post-Merge-Zustand normalisieren — die 5-Zeilen-
     Sondersmoothing-Logik im Adapter ist entfernt.

  Alle 4 Platzierer-Sub-Agents neu trainiert (Bootstrap auf Traces inkl.
  6 neuer EA1-EA6 E-Anchor-Cases in `labeler_platzierer_traces.py`).

## 2026-05-13

- **Schema-Cleanup: `start_offset` aus `hole_pattern_linear` entfernt.**
  Phantom-Feld: war in Template-Signatur und Assembler-Aufruf, aber das
  Template hat es nie geometrisch verwendet — die Reihe wird immer um
  `placement.offset_x/y` zentriert (`first_pos = -total_span / 2`). Daraus
  resultierte ein User-fremdes Vokabular ("Startversatz vom Ankerpunkt"),
  das den Pattern-Classifier zu Halluzinationen verleitete. Entfernt aus
  `templates.hole_pattern_linear`, `assembler._generate_subtract` und
  M_kombo m05 (Spec + Resolver-Goldens). Vier Klassifizierer-Demos, die
  das Feld referenzierten, aus den Traces entfernt; Pattern-Classifier
  ohne sie neu trainiert (Dev 1.00).

- **Splitter: Param-Tails verschmelzen mit Vorgaenger-Aktion.**
  `_PARAM_CONTINUATION_RE` in `aktions_splitter` erkennt Fragmente wie
  "5 tief", "von <kante>", "aus mitte", "X grad", "randabstand",
  "auf teilkreis", "ankerpunkt" als Fortsetzung — sie haengen sich an
  die vorige Aktion an, statt eigene (oft sinnlose) Aktionen zu werden.

- **Default-Orientation fuer Seiten-Flaechen: `<a>x<b>_liegt_auf`.**
  `position_builder._orientation_largest_face_default` setzt fuer
  Seitenflaechen (vorne/hinten/rechts/links) den Liegt-auf-Hint mit
  groesserer Kante zuerst, wenn das Teil 3 distinkte Dimensionen hat.
  Fixt E_kombo e01 (Plattendreh-Default ohne expliziten User-Hint)
  ohne `>Z`/`<Z`-Faelle zu beruehren.

- **N_kombo Slot-Resolver-Erwartung an `pocket_edge_distances` angepasst.**
  Konsistent mit Slot-Footprint-Konvention: `edge_distances` →
  `pocket_edge_distances`, `offset_x` 20 → -5 fuer die V2-Slot-Seite.

- **Inventar Step A: Pro-Teil-Chunking ([ADR 0007](docs/decisions/0007-inventar-step-a-pro-teil-chunking.md)).**
  Deterministischer `teil_splitter` schneidet Specs an Teil-Deklarationen
  (`<typ> mit ...`), `inventar_agent.extract_teile_chunked` ruft pro Chunk
  einen 1-Teil-Micro-Call. Aktiviert erst ab >4 Deklarationen (komplexe
  Multi-Part-Specs). VALID_PARAM_KEYS-Whitelist filtert halluzinierte
  Keys, `decl.split(",", 1)[0]` strippt Platzierungs-Noise vor dem Call.
  Post-Filter `_relabel_features_on_self` in `planning_inventory_nodes`
  verschiebt "auf der/dem <teil_id> ..."-Saetze von Placement zu
  Feature-Saetzen, damit Bohrungen/Taschen auf Sub-Teilen nicht als
  Platzierung des Sub-Teils gelesen werden.

- **Generate-UI kann Goldens direkt starten.** Der erste App-Tab listet
  jetzt wahlweise Pipeline-Goldens aus `tests/golden/<slug>/spec.txt` oder
  runnable Component-Golden-Varianten aus
  `tests/golden/components/<slug>/pipeline/specs.txt`, laedt den Spec in das
  Prompt-Feld und kann den ausgewaehlten Golden als frischen normalen
  Pipeline-Run ausfuehren. Die Ergebnisse laufen dadurch durch dieselbe
  Preview-, Blueprint-, Code-, Trace- und Feedback-Anzeige wie manuelle Runs.

- **V2-Nut-Kantenabstand aus Run `adbf823d` korrigiert.** Der Slot-Resolver
  verwendet bei `slot`-Features nun `width` + `length` als face-lokalen
  Footprint fuer Kantenplatzierung. `5x3` bleibt dabei Breite/Tiefe;
  `laenge=40` bleibt die separate Nut-Laenge. Das V2-Resolver-Golden erwartet
  fuer die obere Y-Nut jetzt `offset_x=-45.5`, `offset_y=7.0`, sodass die
  Nut 18mm Abstand zur oberen Kante haelt statt an der Kante zu starten.

## 2026-05-12

- **Golden-/Trainingsdaten-Coverage auditiert und V2-Palette angelegt.**
  Neuer Audit:
  `docs/golden_coverage_audit_2026-05-12.md`. Neues Component-Set
  `tests/golden/components/V2_balanced_feature_palette/` mit Resolver-,
  Splitter- und Pipeline-Spec fuer eine dichte, aber unterstuetzte
  Standardfeature-Palette: Bohrungen, Taschen, Nuten, Pattern und Features
  auf einer additiven Platte. Dazu 13 passende
  Klassifizierer-Seeds und 13 Normalizer-Kurzform-Seeds. Bewusst nicht als
  expected trainiert: Counterbore/Countersink, Linear-Pattern `start_offset`
  und Kantenfeatures, solange die Codegen-/Executor-Geometrie dort noch
  nicht sauber verdrahtet ist. Gefilterter V2-Real-Smoke ist gruen
  (`1 PASS / 0 FAIL`).

- **Bohrungsreihe-Achsen deterministisch konserviert.** Normalizer/Builder
  uebernehmen `richtung` jetzt fuer `bohrungsreihe` entweder aus
  Klassifizierer-Hints oder direkt aus `entlang x/y/z(-achse)` im Text und
  schreiben sie als `params.direction`. Damit bleibt die Achse im Blueprint
  golden-faehig, ohne sie nur in freien Notes zu verstecken.

- **Modifier-Templates an Assembly-Aufruf angepasst.** V2-Real-Smoke deckte
  auf, dass `chamfer`/`fillet`/`shell` im Assembly-Pfad wie andere
  Child-Operationen mit `(body, _ref)` aufgerufen werden, die Templates aber
  nur `body` akzeptierten. Modifier-Template-Signaturen akzeptieren nun
  optional `_ref`; neuer Test `tests/tools/test_assembler_modifiers.py`.

- **Heatmap-Rekord 15/2.** Bericht:
  `data/sessions/heatmap_20260512_204022.md`. Nur noch zwei Fails,
  beide `aktions_splitter` (E_kombo Plate-Segmentierung in Inventar
  Step A, M_kombo fehlende Pattern-Phrase). Alle anderen Layer
  (feature_definierer, blueprint_resolver, function_decomposer,
  executor, coordinate_validator, geometry_precheck) komplett sauber.
  Drei Fixes seit 14/3:
  - **EF Component-Golden Nut-Notation auf N_kombo-Konvention.**
    `"nut 30x5 entlang x-achse 3 tief"` war mehrdeutig (AxB = breite×tiefe
    ODER laenge×breite, plus widerspruechliches "3 tief"). Umgeschrieben zu
    `"nut 5x3 entlang x-achse laenge 30mm"` — breite=5, tiefe=3, laenge
    explizit. klassifizierer_traces.py + normalizer_traces.py entsprechend
    auf konsistente "AxB = breite×tiefe, laenge explizit"-Demos umgestellt
    (kaputte "AxB + X tief"-Traces entfernt). EF jetzt PASS.
  - **Normalizer "jeweils von den kanten X"-Disambiguierung.** Bei einer
    SINGLE-Bohrung an Eck-Position ("unten rechts ... jeweils 10mm von
    den kanten") sind nur die ZWEI impliziten Kanten gemeint — "alle vier"
    gilt nur bei "an jeder ecke"/eckbohrungen. 4 neue Demos in
    normalizer_traces.py. B_kombo_bohrungen_oben jetzt PASS.
  - **hole_classifier "aus mitte nach <side>" = versatz_*, nicht abstand_*.**
    Run f75a99d4 (B3 v1): "90mm aus mitte nach links" wurde als
    abstand_links=90 (Kantenabstand) statt versatz_links=90 (Mitten-Versatz)
    extrahiert → Resolver bekam widerspruechliche edge+center auf gleicher
    Achse → offset_x falsch. 3 neue hole-Demos fuer "aus mitte"-Wording.
    B3 v1 jetzt PASS.

- **Heatmap-Rekord 14/3 (Zwischenstand).** Bericht:
  `data/sessions/heatmap_20260512_182510.md`. Drei vorher hartnaeckige
  Fail-Layer komplett eliminiert: `function_decomposer`,
  `blueprint_resolver`, `executor`. Verbleibend: zwei `aktions_splitter`
  (E_kombo Plate-Segmentierung, M_kombo 2x2-Grid) und ein
  `feature_definierer` (EF slot_classifier nut-Laenge bei AxB-Notation).

- **Splitter Post-Hoc Param-Continuation-Merge — deterministischer
  Fix fuer dropped Comma-Tails.** Neuer Helper `_is_param_continuation`
  in `src/tools/aktions_splitter.py`: Comma-Fragments ohne Feature-Trigger
  die nur Parameter ergaenzen (`X tief`, `aus mitte X nach Y`,
  `entlang X-achse`, `X grad gegen uhrzeigersinn`, `von <kante> X`,
  `im uhrzeigersinn` etc.) werden an die letzte Aktion desselben
  `teil_id` angehaengt statt zu droppen. Adressiert B3 v1 (run f1744b99)
  wo "10 tief" und "90mm aus mitte nach links" weggeworfen wurden, weil
  sie keine Feature-Trigger enthielten. 10 Unit-Tests in
  `tests/tools/test_aktions_splitter_param_continuation.py` decken
  Kanonisches, Cross-Teil-Schutz, Orphan-Drop, und Regressions-
  Sicherheit fuer den bestehenden pre-feature anchor prefix.

- **Klassifizierer-Split Phase D abgeschlossen — alle 5 Sub-Classifier
  adoptiert.** `pocket_classifier`, `slot_classifier`, `pattern_classifier`
  und `edge_feature_classifier` aktiviert (active=True in
  `data/dspy_training/agent_contracts.py`, Runtime-Flags in
  `config/config.yaml` auf `true`). Trainiert mit erweiterten Trace-Sets
  (insgesamt +11 hand-kuratierte Gap-Filler in `klassifizierer_traces.py`
  fuer pocket "deren X kante", slot CCW/CW Rotations-Vorzeichen und
  "AxB entlang ... C tief"-Notation, pattern 2x2-Grid und Lochreihe
  mit Anker+Startversatz). Final-Dev-Scores: hole 0.79, pocket 0.93,
  slot 0.91, pattern 0.79, edge_feature 1.00.

- **Heatmap 13/4 stabil mit Sub-Classifier-Split.** Bericht:
  `data/sessions/heatmap_20260512_175745.md`. Verglichen mit dem
  Monolith-Stand 13/4 (Commit fd90252) sind drei vorher hartnaeckige
  LLM-Bugs strukturell geloest (B1 v2 Wert-Swap, B_kombo_additive_anchor
  Anker, T_kombo Pocket-Edge-Coin-Flip) — im Tausch verlagern sich zwei
  Fails auf vorgelagerte Layer (B3 v1 Normalizer-LLM-Noise,
  EF slot-Length-Parse). E_kombo und M_kombo bleiben Splitter-Themen.
  Alle 4 verbleibenden Fails liegen jetzt VOR oder NEBEN den
  Klassifizierern — der Klassifizierungs-Layer ist effektiv geklaert.

- **Normalizer-DSPy-Contract auf Runtime-Kurzform korrigiert.**
  `normalizer` trainiert jetzt auf `typ:/seite:/position:/parameter:` statt
  auf nachgelagertem SemanticFeature-JSON. Die bestehenden Feature-Traces
  werden per Adapter in dieses Kurzformat projiziert; noch nicht
  deterministisch unterstuetzte Alt-Typen wie Counterbore/Countersink werden
  aus dem Normalizer-Training gefiltert. Zusaetzlich gibt es direkte
  Gap-Filler-Seeds fuer `kante_*`, `versatz_*`, Pattern, Slot-Achsen,
  Rotation, Fase/Rundung und `aushoelung`. Aktuelle Stats: `normalizer`
  `245` Trace-Pairs + `21` Seed-Pairs = `266` Gesamt.

- **Klassifizierer-Subagent-Coverage nachgezogen.**
  Pattern-Seeds trainieren jetzt nicht mehr nur grob `durchmesser`, sondern
  auch explizite Pattern-Hints (`anzahl`, `kreis_durchmesser`, `abstand`,
  `abstand_kante`, `richtung`). Slot-Seeds decken `rotation_deg`, und
  Pocket-Hint `hoehe` wird im Normalizer deterministisch zu `tiefe`
  gemappt. Aktuelle Stats: monolithischer Klassifizierer `85` Seed/Trace-
  Gesamt, `hole_classifier` `27`, `pocket_classifier` `24`,
  `slot_classifier` `14`, `pattern_classifier` `10`,
  `edge_feature_classifier` `10`.

## 2026-05-11

- **ADR 0006 Phase D gestartet: `hole_classifier` adoptiert.**
  Separates DSPy-Training fuer `hole_classifier` mit 27 Pairs ergab
  Dev-Score `0.90` und erzeugte
  `data/dspy_optimized/hole_classifier_optimized.json` (gezielt versioniertes
  adoptiertes Artefakt). `classifier_subagents.hole_enabled` ist jetzt `true`
  und der DSPy-Contract `hole_classifier` ist aktiv;
  B-Heatmap mit aktivem Sub-Agenten:
  `.venv/bin/python -m scripts.run_real_goldens --filter B --no-persist --no-jsonl`
  -> `11 PASS / 0 FAIL`. Der zunaechst rote `B_kombo_additive_anchor`
  war kein Hole-Classifier-Ausfall, sondern ein Splitter-Verlust von
  comma-getrennten Corner-Anchor-Prefixes. Fix in `src/tools/aktions_splitter.py`
  plus neue Component-Golden unter
  `tests/golden/components/B_kombo_additive_anchor/splitter/`.
  Cross-Family-Smoke `EF,T,NEST,M --first-only` ergab `EF`/`NEST` PASS und
  bestaetigte bestehende separate Fails in `M` (Pattern/Splitter) und `T`
  (Pocket/Resolver kante-vs-abstand).

- **ADR 0006 Phase C umgesetzt: Dispatcher, Flags und Fallback.**
  `aktions_klassifizierer_node` erkennt mit
  `detect_classifier_subagent(phrase)` eindeutige Sub-Agent-Ziele und routet
  nur dann zu `hole/pocket/slot/pattern/edge_feature_classifier`, wenn das
  passende Flag unter `classifier_subagents.*_enabled` gesetzt ist. Alle
  Flags sind per Default `false`, daher bleibt die Runtime ohne Adoption
  identisch zum Monolithen. Bei deaktiviertem Flag, ambigen Phrasen oder
  Sub-Agent-Fehlern faellt der Node auf `AktionsKlassifizierer` zurueck und
  schreibt `routes` in den Trace. Config enthaelt Modelle/Agent-Options fuer
  die Sub-Agenten. Tests:
  `.venv/bin/python -m pytest tests/agents/test_classifier_sub_agents.py
  tests/agents/test_aktions_chain_nodes.py tests/test_dspy_training_variations.py
  tests/agents/test_aktions_klassifizierer.py
  tests/agents/test_normalizer_define_feature.py -q` -> `73 passed`.

- **ADR 0006 Phase B umgesetzt: Klassifizierer-Sub-Agent-Codepfad.**
  Neuer Runtime-Codepfad in `src/agents/classifier_sub_agents.py` mit
  `HoleClassifier`, `PocketClassifier`, `SlotClassifier`,
  `PatternClassifier` und `EdgeFeatureClassifier`. Jeder Sub-Agent hat eine
  eigene schmale Prompt-Datei in `data/prompts/prompt_classifier_*.py`,
  laedt spaeter eigene DSPy-Artefakte per Agent-Name und liefert weiterhin
  den ADR-0003-kompatiblen Output `{typ, seite, parameter_hints}`. In
  `train_dspy.py` nutzen die fuenf Sub-Targets jetzt eigene schmale
  DSPy-Signatures/Module statt der generischen Monolith-Signature. Runtime-
  Routing bleibt fuer Phase C offen. Tests:
  `.venv/bin/python -m pytest tests/agents/test_classifier_sub_agents.py
  tests/test_dspy_training_variations.py tests/agents/test_aktions_klassifizierer.py
  tests/agents/test_normalizer_define_feature.py -q` -> `57 passed`;
  `.venv/bin/python train_dspy.py --stats` gruen.

- **ADR 0006 Phase A umgesetzt: Klassifizierer-Sub-Contracts ohne Runtime-
  Aenderung.** `data/dspy_training/agent_contracts.py` hat nun fuenf
  inaktive typ-spezifische DSPy-Ziele: `hole_classifier`,
  `pocket_classifier`, `slot_classifier`, `pattern_classifier` und
  `edge_feature_classifier`. Die Adapter filtern aus derselben
  Klassifizierer-Seedquelle, damit keine Doppelpflege entsteht.
  `train_dspy.py --stats` weist die Sub-Spalten separat aus:
  initial hole `27`, pocket `23`, slot `13`, pattern `10`, edge `10`
  Gesamtpairs.
  Drei Pattern-Seeds wurden ergaenzt, damit auch `pattern_classifier` die
  ADR-Mindestbasis von 10 Pairs erreicht. Runtime-Routing bleibt bewusst
  unveraendert und faellt weiter auf den Monolithen zurueck. Tests:
  `.venv/bin/python -m pytest tests/test_dspy_training_variations.py
  tests/agents/test_aktions_klassifizierer.py
  tests/agents/test_normalizer_define_feature.py -q` -> `51 passed`.

- **Heatmap-Stand 12/5 (Baseline war 11/6).** Drei Netto-Gewinne durch
  drei voneinander unabhaengige Eingriffe; ein Tasche-Coin-Flip-Verlust
  durch latenten Klassifizierer-LLM-Bug. Bericht:
  `data/sessions/heatmap_20260511_210435.md`. Folgeaufgaben in ADR 0006.

- **ADR 0006 — Klassifizierer-Split + nachfolgende Sub-Agent-Splits**
  (`docs/decisions/0006-classifier-split-and-future-splits.md`). Planung:
  `aktions_klassifizierer` analog Platzierer in 5 typ-spezifische
  Sub-Agents zerlegen (`hole/pocket/slot/pattern/edge_feature_classifier`),
  additive Migration mit Dispatcher + Fallback auf den Monolithen.
  Danach im gleichen Pattern: `plan_validator` (pro Aspekt), `normalizer`
  (per-Feature-Typ oder Konsolidierung mit Klassifizierer), spaeter
  `feature_definierer` und ggf. `position_extractor`. Begruendung: empirisch
  belegte Cross-Contamination im Monolith-Training (siehe naechster Punkt).

- **Klassifizierer-Monolith-Aktivierung getestet, dann zurueckgerollt.**
  Mit 78 Pairs (70 Seed + 8 Trace) trainiert (Dev-Score 0.88). Heatmap-Diff:
  +B1 v2 PASS (Wert-Swap-Bug deterministisch fixbar), aber -EF und -T_kombo
  durch Tasche-Demo-Cross-Pollution → Netto -1. Rollback: `active=False`
  in `data/dspy_training/agent_contracts.py`, optimized JSON umbenannt zu
  `data/dspy_optimized/aktions_klassifizierer_optimized.json.disabled_tasche_regress`.
  Lehre: Monolith-Training skaliert nicht ueber Feature-Typen → Split-
  Architektur als richtige Antwort (siehe ADR 0006).

- **Deterministischer Post-Filter in `position_extractor_node` fixt EF-
  Mis-Split.** Neuer Helper `_relabel_features_on_self` in
  `src/graph/nodes/planning_inventory_nodes.py`: verschiebt Saetze die
  mit `auf der/dem <teil_id>` oder `in der/dem <teil_id>` beginnen aus
  `placement_sentences` in `feature_sentences`. Adressiert deterministisch
  den LLM-Labeler-Mis-Split, der bei EF-Specs Feature-on-self-Saetze
  faelschlich in placement legt. Folge: Platzierer-Offset-Step bekam
  noisy pos_spec und extrahierte Spurious-Werte → Plate landete bei
  offset_x=23 statt 0. 10 Unit-Tests in
  `tests/graph/test_position_extractor_relabel.py` decken Kanonisches,
  Parent-Referenzen (bleiben in placement), Case-/Whitespace-Robustheit,
  Suffix-IDs, Mehrfach-Verschiebungen ab.

- **`feature_builder` routet `pocket_edge_distances` nur noch fuer
  rechteckige Subtraktiv-Features.** Aenderung in
  `src/tools/feature_builder.py`: wenn der LLM `kante_*`-Keys auf Bohrungen
  oder Kantenfeatures (chamfer, fillet, shell, alle hole_*) leakt, werden
  sie in `edge_distances` (edge-to-center) umgeleitet statt in
  `pocket_edge_distances` (edge-to-edge), damit der Resolver nicht
  child_half subtrahiert. Behebt B3 v1 (Run bc28acc5): hole_single mit
  spurious pocket_edge_distances `{top:10}` ergab offset_y `81` statt `90`
  (90 = erwartet, 81 = 90-9_radius). Heatmap: B3 v1 stabil PASS, 0
  Regressions in den 4 anderen B*-Specs.

- **`labeler_platzierer_traces.py` um 20 Traces erweitert (Z/ZR/V/EF
  Serien) und alle 4 Platzierer-Sub-Agents nachtrainiert.** Neue
  Kategorien: 6× pure zentral (verschiedene Faces/Sizes/Wording),
  2× zentral+Rotation, 2× pure Versatz, 8× EF-Noise (placement_sents
  mit nachgelagerten "auf der platte..."-Saetzen + Output simpel zentral).
  Adressiert Class-Imbalance der vorherigen 21 Traces (zu wenig
  Pure-zentriert-Demos) und das Bootstrap-Problem dass Hard-Cases nicht
  gewaehlt wurden. Dev-Scores: frame 0.96, alignment 0.83, offset 0.95
  (vorher 0.60 monolithisch). Stuetzt unter anderem den oben genannten
  Post-Filter-Fix fuer EF.

- **DSPy-Inventar-Retraining adoptiert.** Mit 222 Pairs (Trace + Legacy)
  trainiert, Dev-Score 0.95. Heatmap-Diff: +B2 v1 PASS stabil ueber
  zwei verifizierte Runs. Eliminiert die `function_decomposer` und
  `feature_definierer` Fail-Layer ganz aus der Heatmap. Backup unter
  `inventar_optimized.json.bak_baseline_20260510_232326`. Andere
  DSPy-Retrainings derselben Session (position_extractor, platzierer
  monolithisch, normalizer) sind als neutral oder regressiv eingestuft und
  entweder zurueckgerollt (position_extractor) oder als Sub-Agent-Variante
  ersetzt (platzierer); Details und Lessons in Memory
  `feedback_dspy_retraining_discipline.md`.

- **runs.jsonl archiviert und neu gestartet.** Pollution durch nicht
  zuverlaessig markierte Bad-Runs unterbunden — neue Datei ist leer,
  alte unter `data/sessions/runs.jsonl.archive_20260510_233100`. Bis
  ein `--annotate-runs`-Mechanismus in `scripts/run_real_goldens.py`
  existiert (Memory: `feedback_dspy_retraining_discipline.md`) hilft das
  als Schutz vor versehentlichem Bulk-Marker-Schaden.

- **Klassifizierer-Seedbasis deutlich verbreitert und validiert.**
  `data/dspy_training/klassifizierer_traces.py` enthaelt nun 72 direkte,
  hand-kuratierte Phrase-Level-Beispiele fuer den `aktions_klassifizierer`
  statt 3: `bohrung`, `tasche`, `nut`, `fase`, `rundung` ueber alle sechs
  Seiten, inklusive Center-Abstand, explizitem Edge-to-Edge, Versatz,
  Rotationsvorzeichen, Parent-Seitenvererbung, Kombi-nahe Nested-Faelle,
  Pattern-Phrasen (`lochkreis`, `eckbohrungen`, `bohrungsreihe`) als grobe
  `bohrung`-Familie sowie adjektivische Seitenformulierungen
  (`rechte Seite`, `obere Flaeche`, `Unterseite`). Der Klassifizierer-Contract
  erlaubt additiv `parameter_hints.richtung = x|y|z` fuer explizite
  `entlang <Achse>`-Phrasen; der Normalizer hebt diesen Hint vor der
  Slot-Laengen-Inferenz auf das top-level Feld `richtung`. Der Seed bleibt
  strikt im bestehenden Contract: keine neuen Typen, keine neuen Seiten, nur
  bekannte `parameter_hints` und nur explizite Werte.
  `tests/test_dspy_training_variations.py`
  validiert Count, eindeutige IDs, erlaubte Typen/Seiten/Hint-Keys und
  numerische Hint-Werte sowie Mindestabdeckung fuer Nested-, Pattern- und
  Seitenadjektiv-Faelle. Statistik danach: `aktions_klassifizierer
  (inactive)` mit 8 Trace-, 72 Seed- und 80 Gesamtbeispielen. Tests/Checks:
  `.venv/bin/python train_dspy.py --stats`; `.venv/bin/python -m pytest
  tests/test_dspy_training_variations.py tests/agents/test_normalizer_define_feature.py
  -q` -> `37 passed`; Pycompile der geaenderten Trainingsdateien gruen.

- **Platzierer-Anchor-Traces um fehlende Corner-Anker ergaenzt.**
  `labeler_platzierer_traces.py` deckt im Split-Training fuer
  `platzierer_anchor` nun auch `bottom_left`, `bottom_right` und diagonale
  Corner-Paarungen (`top_left` auf `bottom_right`, `bottom_right` auf
  `top_left`) ab. Statistik danach: `platzierer_anchor` 9 Trace-Beispiele;
  Frame/Alignment/Offset jeweils 39.

- **Platzierer-DSPy-Training in Runtime-kompatible Mini-Contracts
  gesplittet.** Der alte monolithische `platzierer`-Trainingscontract ist
  inaktiv, weil dessen `normalized_position`-Demos im falschen Format in alle
  vier Runtime-Mini-Calls eingespeist wurden. Neue aktive Trainingsziele:
  `platzierer_frame`, `platzierer_alignment`, `platzierer_anchor` und
  `platzierer_offset`. `PositionNormalizerAgent` laedt nun step-spezifische
  DSPy-Artefakte und injiziert sie nur in den passenden Mini-Prompt. Die
  Trainingsprojektion filtert alte Sonnet-Platziererlabels mit Legacy-
  Vokabular aus und nutzt nur current-schema Labels fuer die Split-Ziele.
  Der Train/Dev-Split ist stabil gemischt, damit kleine kuratierte Packs
  nicht nach Kategorie in Train/Dev zerfallen. Neu erzeugte labeled-only
  Artefakte: `platzierer_frame_optimized.json`,
  `platzierer_alignment_optimized.json`, `platzierer_anchor_optimized.json`,
  `platzierer_offset_optimized.json`. Dev-Scores nach Korrektur:
  Frame `1.00`, Alignment `1.00`, Anchor `1.00`, Offset `1.00`.
  Tests/Checks: `.venv/bin/python train_dspy.py --stats`;
  `.venv/bin/python -m pytest tests/test_dspy_training_variations.py -q`
  -> `5 passed`; Pycompile der geaenderten Trainings-/Agent-Dateien gruen;
  Runtime-Demo-Load-Check -> `13/13/4/10` nicht-leere Demos.

## 2026-05-10

- **DSPy Variation Pack 1 fuer natuerliche CAD-Formulierungen angelegt.**
  `data/dspy_training/variation_traces.py` ergaenzt 8 kuratierte
  Trainings-Traces fuer Sprach-/User-Varianten ohne neue Runtime-Regex:
  Bauteil-Mass-Reihenfolgen (`bei einem 200mm Wuerfel`,
  `Wuerfel mit 75mm`, `Quader mit den Massen ...`, `200er Platte`),
  fehlendes Komma nach dem Grundkoerper, Kanten-/Seiten-Abstaende mit
  unterschiedlichen Werten (`18`, `21`, `23`, `31`), Edge-to-Edge-
  Formulierungen und Center-Versatzvarianten (`16/24`, `19/26`). Der
  `aktions_klassifizierer` kann nun ueber `train_dspy.py --agent
  aktions_klassifizierer` trainiert werden, bleibt aber fuer `--all`
  inaktiv. Batch-Traces aus `runs.jsonl` werden dafuer in phrase-level
  Beispiele expandiert. Statistik danach: 202 Pipeline-Traces,
  `aktions_klassifizierer (inactive)` mit 8 Trace-, 323 Run- und 3
  Seed-Beispielen, Gesamt 334. Tests:
  `uv run pytest -q tests/test_dspy_training_variations.py
  tests/agents/test_aktions_klassifizierer.py
  tests/agents/test_inventar_aliases.py` -> `30 passed`;
  `uv run python train_dspy.py --stats` gruen; Fast Gate
  `uv run pytest -q --ignore=tests/golden` -> `289 passed`.

- **B_kombo_asymmetric_multiface Abschnittsseiten stabilisiert.**
  `aktions_klassifizierer_node` fuehrt nun pro Teil eine deterministische
  Abschnittsseite aus Phrasen wie `oben (...):` oder `rechts (...):`.
  Folgephrasen mit lokalen Positionswoertern (`unten links`,
  `nach unten ...`) erben diese Flaeche, statt als neue Weltseite
  klassifiziert zu werden. Damit ist der bisherige Replay-Fail
  `B_kombo_asymmetric_multiface` im Live-Fokuslauf gruen.
  Tests: `uv run pytest -q tests/agents/test_aktions_chain_nodes.py`
  → `12 passed`; `uv run pytest -q tests/golden/components/test_splitter_components.py tests/golden/components/test_resolver_components.py`
  → `15 passed`; `uv run python -m scripts.run_real_goldens --filter B_kombo_asymmetric_multiface --no-persist --no-jsonl`
  → `1 PASS / 0 FAIL`; Fast Gate
  `uv run pytest -q --ignore=tests/golden` → `286 passed`.

- **EF/NEST/T Anchor-Cluster fokussiert stabilisiert.**
  Nach dem Nuten-Fix waren `T_kombo` live bereits gruen, `EF_kombo`
  scheiterte noch an `ef07` (`rechte kante der bohrung auf rechte kante
  der platte`) und `NEST_kombo` war blueprint-gruen, aber mit
  `coordinate_errors_unresolved` wegen einer bewusst offenen Bohrung an
  der Taschenkante. `NormalizerAgent` erkennt nun explizite
  Child-Edge-Phrasen (`rechte/linke/obere/untere kante der bohrung/...`)
  als `child_point=*_edge`; der Coordinate-Validator stuft teilweise
  ueberstehende subtraktive Feature-in-Pocket-Cuts als Warnung ein,
  vollstaendig ausserhalb liegende Pocket-Children bleiben Fehler.
  Tests: `uv run pytest -q tests/agents/test_normalizer_define_feature.py
  tests/tools/test_coordinate_validator.py tests/graph/test_coord_validator_node.py
  tests/golden/components/test_resolver_components.py -k 'not slow'`
  → `51 passed`; Live-Heatmap
  `uv run python -m scripts.run_real_goldens --filter EF_,NEST_ --first-only --no-persist`
  → `2 PASS / 0 FAIL`, Runs `3adbf438`, `c229d2b0`, beide
  `success=True`. `T_kombo` war im vorigen Fokuslauf ebenfalls PASS
  (`4933a5f7`). Replay-Heatmap danach: `11 PASS / 6 FAIL`; der
  `blueprint_resolver`-Cluster ist aus der Fail-Heatmap raus.

- **N_kombo live gruen: Nuten-Laenge, Face-Achsen, Anchors und Validator.**
  `NormalizerAgent.define_feature` fuellt bei Nuten ohne explizite `laenge`
  die volle Parent-Face-Achsdimension deterministisch aus `teil.raw_params`.
  Slot-Winkel sind jetzt face-lokal (`>Z`: X=0/Y=90, `>X`: Y=0/Z=90).
  Der Splitter haengt reine Versatz-Folgefragmente wie
  `10mm nach oben versetzt` an die vorherige Feature-Phrase, und der
  Normalizer leitet klare Kanten-/Eckenanker (`liegt auf rechter kante`,
  `obere rechte ecke ...`) additiv nach `position.anchor` ab. Der
  Coordinate-Validator behandelt teilweise ueberstehende subtraktive
  Kanten-Cuts als Warnung statt Fehler, vollstaendig ausserhalb liegende
  Features bleiben Fehler. Die Real-Run-Heatmap paart gleiche
  `(type, face, offset)`-Features zusaetzlich ueber Winkel/Parameter, damit
  Nuten mit gleichem Zentrum sauber verglichen werden.
  Tests: gezielte Splitter/Normalizer/Validator/Heatmap-Tests gruen;
  `uv run python -m scripts.run_real_goldens --filter N_kombo --first-only --no-persist`
  → `1 PASS / 0 FAIL`, Run `633015ee`, Pipeline `success=True`.

- **Baseline-Hygiene fuer komplexe Standard-Teile gestartet.**
  Pipeline-Goldens sind als `slow` markiert und werden per Default nicht
  von `pytest` gestartet; Component-Goldens bleiben schnell. Config nimmt
  `models.aktions_klassifizierer` jetzt explizit an, UI-History-Testdrift
  wurde auf die aktuelle Restore-Outputliste synchronisiert, und ein
  gemeinsames Run-Success-Gate verhindert, dass STL-only/leer-Blueprint
  oder unresolved-coordinate Runs als Erfolg in UI/API/Logs erscheinen.
  Die Golden-Doku beschreibt nun die Capability Ladder von Einzel-Features
  bis grossen Kombi-Teilen samt Heatmap-Kommandos.

## 2026-05-09

- **LLM-Layer-Fix-Runde 1: Slot-Achsen-Konvention + Klassifizierer
  Face-zuerst Few-Shot + DSPy-Trainings-Daten.**
  Heatmap-Auswertung nach Splitter-Fix zeigte 4 LLM-Layer-Bugs: 2
  Klassifizierer (B_asym + B_kombo_bohrungen face-mismatches), 2
  feature_definierer (N_kombo angle/length, NEST diameter). Trace-
  Buendel-Analyse aus runs.jsonl, dann Fixes:

  - **NEST Spec-Bug:** mein konstruierter Spec sagte "5mm bohrung",
    expected_resolved.json hatte diameter=8 fuer alle NEST-Bohrungen.
    Korrigiert in [tests/golden/components/NEST_kombo_basics/pipeline/specs.txt].
  - **Slot-Achsen-Konvention deterministisch** in
    [src/tools/feature_builder.py]: notes.md N_kombo definiert
    "entlang x-achse" → angle_deg=0, "entlang y-achse" → angle_deg=90
    (kombiniert mit Rotation: 0+15 oder 90+15). Diese Konvention war
    bisher NICHT codiert — feature_builder hat richtung nur in notes
    geschrieben und angle_deg=0 gelassen. Jetzt: y-Achse mappt
    additiv +90° auf angle_deg. Drei neue Unit-Tests
    (`test_slot_y_axis_sets_angle_deg_90`,
    `test_slot_y_axis_combines_with_explicit_rotation`,
    `test_slot_x_axis_keeps_angle_deg_0`).
    Memory-Begruendung: Aufgaben-Trennung Memory `feedback_determinism_scope`
    — Achsen→Winkel-Mappierung ist Mathe (deterministisch), das LLM
    erkennt nur die Achse aus dem Text.
  - **Klassifizierer Few-Shot fuer Face-zuerst-Pattern** in
    [data/prompts/prompt_aktions_klassifizierer.py]: System-Prompt um
    Block "Mehrere Side-Woerter in einer Phrase" erweitert (erstes bare
    Side-Wort ist Face, spaetere sind Position auf der Face). Plus
    Few-Shot mit User-Phrase "oben soll unten rechts eine 18mm Bohrung
    jeweils von den kanten 10mm entfernt" → seite=oben, abstand_unten:10,
    abstand_rechts:10. Pattern stammt aus Run f28b958a phrase_idx=1.
  - **DSPy-Trainings-Datenfundament gelegt:**
    `data/dspy_training/klassifizierer_traces.py` (3 Cases: Face-zuerst
    fixed + 2 Face-Erbung deferred) und
    `data/dspy_training/feature_definierer_traces.py` (4 Cases: Slot-
    Achsen 2x fixed + Slot-durchgehend-Default + Slot-Anchor-Edge
    deferred). Doppelt nutzbar: DSPy-Material + Few-Shot-Quelle +
    spaetere Regression-Sentinels.
  - **Memory-Defer fuer Architektur-Issues:**
    `project_klassifizierer_face_inheritance_deferred.md` — B_asym
    Phrasen ohne eigene Face-Decl muessen vom geschwister-Vorgaenger
    erben. Klassifizierer-Schema-Erweiterung um `previous_seite`
    (additiv) noetig — separates Refactor.

  **Heatmap-Effekt:**
  | Layer | nach Splitter | nach LLM-Runde |
  |-------|--------------:|---------------:|
  | aktions_splitter | 2 | 2 (Spec-Coverage + E_kombo deferred) |
  | aktions_klassifizierer | 2 | 1 (B_bohrungen PASS, B_asym deferred) |
  | blueprint_resolver | 2 | 3 (NEST n6 anchor-in-tasche jetzt sichtbar) |
  | feature_definierer | 2 | 1 (N_kombo angle behoben, length offen) |
  | function_decomposer | 2 | 2 |
  | executor | 1 | 1 |
  | **Total** | 11 FAIL | **10 FAIL / 7 PASS** |

  B_kombo_bohrungen_oben gruen geworden, NEST von 20 Diffs auf 2.
  262/262 Unit-Tests + 15/15 Component-Goldens gruen.

- **Splitter-Fix-Runde 1: Plural/Komposita + Semicolon-Top-Level-Split**
  ([src/tools/aktions_splitter.py]). Erste Heatmap-Auswertung nach
  strukturellem Pairing zeigte 3 Drop-All-Cases unter
  `aktions_splitter` (M_kombo, B_kombo_asym, E_kombo). Trace-Analyse:

  - **M_kombo (Run 5cc0bb53):** `_FEATURE_RE` matcht `\bbohrung\b`,
    nicht aber `bohrungen` (Plural-Suffix-`en`) und auch nicht die
    Loch-Komposita `lochmuster`/`lochkreis`/`lochreihe` (kein
    Wortgrenze nach `loch`). Konsequenz: jede Mustertyp-Phrase wird
    gedroppt, Pipeline produziert 0 Features.
  - **B_kombo_asym (Run 69931839):** User-Spec verwendet `;` als
    Top-Level-Separator. `_comma_split` splittet nur an `,`, also
    landet alles in einer Mega-Phrase. Klassifizierer kann mit 6
    verschachtelten Aktionen in einer Phrase nichts anfangen.
  - **E_kombo (Run 55863562):** Nicht ueber Splitter heilbar — Inventar
    segmentiert die 12 "vorne soll eine platte 80x40x20"-Phrasen als
    11 Teile statt 1 Teil + 12 Plate-Features. Multi-Part-Anchor-Pfad,
    architektonische Entscheidung noetig (Memory
    `project_e_kombo_multipart_deferred`). Deferred.

  **Fix:**
  - `_FEATURE_RE` Stems um enumerierten Suffix erweitert:
    `tasche(?:n)?`, `bohrung(?:en)?`, `nut(?:en)?`, `fase(?:n)?`,
    `rundung(?:en)?`, `loch(?:muster|kreis|reihe|bild|er)?`,
    `ausnehmung(?:en)?`, `aush[oö]hlung(?:en)?`,
    `ausfr[äa]sung(?:en)?`, `aussparung(?:en)?`. Konservativ —
    keine Wildcard-`[a-z]*` um false positives wie `fasern`/`nutzbar`
    zu vermeiden.
  - `_comma_split` erweitert auf Regex `[,;]` (semicolons als
    semantisch-aequivalenter Top-Level-Trenner).

  **Goldens (GE-FIXED-Pattern aus Memory `project_goldens_workflow_2026_05_08`):**
  - `tests/golden/components/M_kombo_basics/splitter/` — 5 Phrasen
    erwartet, vor Fix 0 (rot), nach Fix gruen.
  - `tests/golden/components/B_kombo_asymmetric_multiface/splitter/` —
    6 Phrasen erwartet (eine Phrase pro `;`-Segment), vor Fix 1 Mega-
    Phrase (rot), nach Fix gruen.

  **Heatmap-Effekt** (Replay-Modus):
  - aktions_splitter: 3 → 2 (M_kombo verliert nur noch 1 Feature wegen
    Spec-Coverage-Luecke m02, E_kombo bleibt deferred).
  - aktions_klassifizierer: 1 → 2 (B_asym jetzt sichtbar als
    face-mismatch `>X`→`<Z` — vorher von Splitter-Drop verdeckt).
  - Pipeline lebt, downstream-Bugs werden sichtbar — bug-by-bug-
    Drilldown wirkt.

  259 Unit-Tests + 15/15 Component-Goldens (3 Splitter, 12 Resolver)
  gruen.

- **Strukturelles Feature-Pairing im Real-Run-Heatmap-Compare +
  Replay-Modus.**
  Erste Heatmap-Runde 2026-05-08 hatte 11/17 Fails, davon 6 false
  positives durch reines ID-Matching: `compare_blueprints` hat Features
  nach ID gepaart, aber `expected_resolved.json` traegt handverlesene
  IDs (`t05_pocket_edge_top_left`) waehrend die Pipeline auto-IDs
  (`tasche_oben_4`) erzeugt. Identische Geometrie wurde als
  "missing+unexpected" gemeldet, Layer faelschlich `blueprint_resolver`.

  - [scripts/run_real_goldens.py] `compare_blueprints` umgebaut auf
    strukturelles `_pair_level`: paart Sibling-Features pro Parent-
    Ebene zuerst per `(type, face)`-Signatur, dann innerhalb gleicher
    Signatur per offset-distance-Greedy. Rekursiv ueber Parent-Pairs
    hinweg, sodass NEST-Bohrungen (parent=tasche_a vs parent=
    tasche_oben_0) korrekt ueber die Tasche-Pairing weiter geleitet
    werden.
  - `attribute_layer` erkennt jetzt face-mismatches zwischen unmatched
    expected/got (z.B. 1 fehlt auf >Z, 1 extra auf <Z → Klassifizierer-
    Side-Bug). Total-Feature-Count statt Per-Root-Count fuer Splitter-
    Drop-Detection (Pairing macht Per-Root-Korrelation schon).
  - Neuer `--replay`-Modus: liest persistierte Heatmap-Runs aus
    `data/sessions/runs.jsonl` (task_id=real_goldens_heatmap) und
    re-evaluiert sie offline gegen die aktuelle expected — spart ~20
    min LLM-Pipeline bei Compare-Logik-Iterationen.
  - Neue Heatmap (Replay): 6 PASS / 11 FAIL, sauber aufgeteilt:
    aktions_splitter=3, blueprint_resolver=2, feature_definierer=2,
    function_decomposer=2, aktions_klassifizierer=1, executor=1.
    Vorher pauschal blueprint_resolver=5 — die 3 Fehlattribuierten
    sind jetzt korrekt feature_definierer (N angle/length, NEST
    diameter) bzw. aktions_klassifizierer (B_kombo_bohrungen_oben
    bohrung_unten_1 statt bohrung_oben_*).

## 2026-05-08

- **Coder-Skip global per `error_loop.disable_coder` (Default: true) +
  Heatmap-Runs persistieren in runs.jsonl.**
  Memory `project_coder_elimination` und
  `feedback_template_mode_no_coder` haben den Coder schon laenger als
  Eliminations-Kandidat markiert; in Real-Runs wird er trotzdem
  haeufig aktiviert (placement-error im Validator, llm-Modus aus
  function_decomposer, phase=1 im Error-Router) und kostet Zeit ohne
  Mehrwert. Jetzt deterministisch geblockt.

  - Neuer Config-Flag `error_loop.disable_coder: bool = True` in
    [src/config/loader.py] und [config/config.yaml]. Default true —
    der alte Coder-Pfad ist via `disable_coder: false` reaktivierbar.
  - [src/graph/edges.py]: drei Routes umgelenkt.
    `route_after_executor` short-circuited zu END (zusaetzlich zum
    bereits existierenden template-mode-Bypass), `route_after_validator`
    placement-error → END statt coder, `route_after_error_router`
    skipt phase=1 + phase=2 → END.
  - [src/graph/pipeline.py]: zwei weitere Routes.
    `route_after_function_decomposer` llm-mode + disabled → END
    (Conditional-Edge-Mapping um `"end": END` ergaenzt),
    `route_after_code_review` issues + disabled → executor (durchwinken,
    Code-Review wird nicht kuenstlich blockiert).
  - Effekt fuer Real-Runs: Pipeline laeuft normal durch alle
    deterministischen Stufen, schliesst auch bei Codegen-/Validator-
    Faults sauber ab (kein STL bei Fail, aber Blueprint+Traces bleiben
    vollstaendig erhalten).
  - [scripts/run_real_goldens.py]: ruft pro Run `SessionLogger.log_run`
    auf — jeder Heatmap-Run bekommt eine `run_id` in
    `data/sessions/runs.jsonl` (mit allen agent_traces fuer Deep-Dive).
    Run-ID erscheint in der CLI-Tabelle (`run=8c4c7498`) und im
    persistenten Heatmap-Markdown. `--no-jsonl` deaktiviert den Append.
  - 244/244 Unit-Tests gruen, 13/13 Component-Goldens gruen, B1-Smoke
    Real-Run PASS in 48s mit run_id-Persistenz verifiziert.

- **Real-Run-Heatmap-Skript fuer Component-Goldens.**
  Neuer Knopfdruck-Workflow fuer den naechsten Roadmap-Schritt aus
  Memory `project_next_real_run_analysis_2026_05_08.md`: Component-
  Spec-Varianten durch die echte LLM-Pipeline schicken und Bug-Heatmap
  pro Layer auswerten.

  - Pro Component (B1-3, B_kombo_*, M/N/T/E/EF/NEST_kombo_basics)
    eine `pipeline/specs.txt` mit einer oder mehreren Spec-Varianten
    angelegt — B1/B2 mit drei Wording-Varianten, B3 mit zwei, restliche
    Components mit der jeweiligen Original-User-Spec aus notes.md.
    Fuer M/E/EF/NEST (notes.md hat dort nur Resolver-Tabellen, keinen
    User-Spec-Block) wurden Specs aus den Tabellen konstruiert und im
    File als KONSTRUIERT markiert — Wording soll bei Real-Run-Auffallen
    iterativ verfeinert werden.
  - Neues Skript `scripts/run_real_goldens.py`. Discovery: jede
    `tests/golden/components/<X>/pipeline/specs.txt` plus
    `<X>/resolver/expected_resolved.json` wird ein Real-Run-Case.
    Filter (`--filter B`, `--filter B1,NEST`), `--first-only` fuer
    Quick-Pass, `--list` fuer Discovery-only.
  - Pro Spec: `PipelineRunner.run`, dann Vergleich des resolved
    Blueprints gegen `expected_resolved.json` mit den gleichen
    Toleranzen wie `test_resolver_components.py`.
  - Heuristische Layer-Attribution: Pipeline-Crash mit error_tag →
    Trace-Agent; root-Teile-Anzahl falsch → inventar; Feature-Count
    pro Teil falsch → aktions_splitter; parent-Rewriting falsch →
    aktions_aggregator (NEST); type/face/side-Diff →
    aktions_klassifizierer; params-Diff → feature_definierer;
    offset/angle-Diff → blueprint_resolver.
  - Output: tabellarische Pro-Spec-Zeile (PASS/FAIL + Layer + erste
    Diagnose), Layer-Heatmap mit ASCII-Bars, persistenter Report
    `data/sessions/heatmap_<datum>_<zeit>.md` mit allen Diffs +
    State-Pointers fuer Deep-Dive.
  - Smoke-Test: `--filter B1 --first-only` PASS in 43.8s gegen die
    B1-v0-Spec. Discovery findet 17 Specs in 12 Components.
  - Vorbereitet fuer ADR 0005 Phase 3: erste Real-Run-Heatmap nach
    Component-Familien (B/M/N/T/E/EF/NEST) liefert die Daten fuer die
    Architektur-Entscheidung Spezialisten-Fan-Out vs. Front-Layer-
    Haerten.

- **Component-Goldens-Coverage komplett (B/M/N/T/E/EF/NEST) +
  Splitter Voice-Resilienz** (Commit `2129818` + Folge-Commit fuer NEST).
  Vollstaendige Phase-A-Coverage aus
  [ADR 0005](docs/decisions/0005-regressions-baseline-feature-matrix.md):

  - **13 Component-Goldens, ~79 Test-Cases**, alle deterministischen
    Resolver-Pfade abgedeckt (B Bohrungen, M Lochmuster mit Grid-Bypass,
    N Nuten, T Taschen mit pocket_edge_distances, E Extrusion-Platten
    Multi-Part-Anchor, EF Features auf Platte, NEST Bohrung-in-Tasche
    mit pocket_floor depth_reference + Rotation-Pre-Multiply).
  - **Splitter Pre-Processor** `_insert_missing_commas` in
    [src/tools/aktions_splitter.py] — Sicherheitsnetz fuer Voice-Input
    wenn Punctuation-Agent das Komma vor `<param-end> <side> soll`
    droppt. Konservative geschlossene Liste (tiefe/hin/versetzt/...)
    plus side-keyword + "soll" → automatischer Komma-Insert vor
    Komma-Split. Run-944d-Pattern als Regression-Sentinel.
  - **Test-Runner** [tests/golden/components/test_splitter_components.py]
    mit Discovery fuer `<scope>/splitter/spec.txt + expected_phrases.json`.
  - **Knopfdruck-Workflow**: `pytest tests/golden/components/` laeuft in
    0.04s und liefert klare Diagnose-Outputs bei Regressionen.
  - **Vorbereitet** fuer Architektur-Pivot (ADR 0005 Phase 4) und
    DSPy-Training (Phase 5) — Schema eingefroren, jede unbeabsichtigte
    Verhaltensaenderung wird durch ~79 Sicherheitsnetze sofort gefangen.

## 2026-05-07

- **Bug A + Bug C + Bug D aus Real-Run-Analyse 8a170a03 / dc21d2ab**
  in einem Folge-Commit. Drei verkettete Probleme, die in den drei neuen
  Real-Runs zutage kamen (Quell-Runs: `8a170a03`, `8ee557ef`,
  `dc21d2ab`).

  - **Bug C: Bug-7-Regression im Anchor-Prompt zurueckgenommen**
    ([data/prompts/prompt_position_anchor.py]). Die "Ecke + Kante
    zusammen genannt → ENDPUNKT der Kante"-Regel hat das LLM verleitet,
    `right_edge_bottom` (Endpunkt) zu waehlen, obwohl der User
    `right_edge` (Mitte) meinte. dc21d2ab zeigte die Plate bei
    `offset_y=-104.5` statt `~ -4.5` (da35a6ce). Korrektur: die
    aggressive Regel + die zwei Endpunkt-Few-Shots durch eine neutrale
    Regel "Kind-Ecke auf Parent-Kante → Mitte der Parent-Kante"
    ersetzt. LUT-Erweiterung aus Bug 7 bleibt — Endpunkt-Vokabular
    nutzt das LLM nur noch wenn der User explizit "Ende der Kante"
    sagt. Few-Shot fuer den expliziten Fall ergaenzt.
  - **Bug A: Splitter laesst Part-Decl-Phrasen nicht mehr durch**
    ([src/tools/aktions_splitter.py]). Phrasen ohne Feature-Keyword
    (tasche/bohrung/nut/fase/rundung/loch/...) werden jetzt im
    `_strip_part_declaration` gedroppt — dropout-Rule wurde von
    "wenn _SIDE_RE nichts findet" auf "wenn _FEATURE_RE nichts findet"
    verallgemeinert. Heilt die Phantom-Pockets aus 8a170a03 / dc21d2ab,
    wo der `aktions_klassifizierer` "vorne soll eine platte hin mit
    140x20x40" und "die 140x20 seite liegt auf davon die rechte untere
    ecke ..." als `typ=tasche` mit den Plattenmassen klassifiziert
    hat — ergab `tasche_vorne_0` und `tasche_unten_1` als phantom
    Subtraktionen auf der Platte. Tests bleiben gruen.
  - **Bug D: Splitter defaultet auf Basis-Teil statt last_teil**
    ([src/tools/aktions_splitter.py]). `_assign_teil_id` Fallback
    `return last_teil` ersetzt durch `return teil_ids[0]`. Heilt
    dc21d2ab ("auf der rechten seite eine bohrung ..." nach
    Platte-Decl landete auf Platte) und 8a170a03 (gleiche Phrasen
    vor Platte-Decl landeten auf Wuerfel — auch korrekt). User-Regel:
    Aktionen ohne expliziten "auf der platte X" oder gleichwertigen
    Ueberordner gehen aufs Basis-Teil. Tests: 2 neue Cases
    (`test_phrases_after_other_part_default_to_base`,
    `test_explicit_other_part_mention_overrides_base_default`),
    `test_unknown_teil_segment_falls_back_to_last_seen` umbenannt.

  Suite 240/240 gruen. **Bug B (text_splitter halluziniert "auf der
  platte" statt "auf der rechten seite")** bleibt offen — wenn Bug A+D
  wirken, wird text_splitter's Output nicht mehr fuer teil_id
  verwendet, daher zurueckgestellt.

- **Bug 7 (ADR 0004): Anchor-Edge-Endpunkte im Vokabular**
  ([src/tools/blueprint_resolver.py], [src/tools/position_builder.py],
  [data/prompts/prompt_position_anchor.py]). Run da35a6ce/e1def0fa-Phrase
  "rechte untere ecke auf der rechten kante 10mm nach oben" mappte
  `parent_point=right_edge` auf den Mittelpunkt der Kante — Plate landete
  mittig statt am unteren Endpunkt. Fix: 8 Endpunkt-Schluessel additiv
  ins `_ANCHOR_POINT_LUT` aufgenommen (`right_edge_top/bottom`,
  `left_edge_top/bottom`, `top_edge_left/right`, `bottom_edge_left/right`)
  plus deutsche Aliase (`rechte_kante_unten`, …). `_H_FLIP_MAP` analog
  erweitert fuer viewer-mirror Faces (<X, >Y). Builder-Whitelist
  `_ANCHOR_POINT_KEYWORDS` um die acht Endpunkte ergaenzt. Position-
  Anchor-Prompt um Vokabular-Block + neue Standard-Regel "Ecke + Kante
  zusammen genannt → Endpunkt" + zwei Few-Shots erweitert. Resolver
  bleibt regel-arm, kein Heuristik-Fallback. Tests: +6 in
  `test_anchor_placement.py` (inkl. da35a6ce-Smoke-Test mit 200³ Cube,
  140x20x40 Plate, 20° CCW), +2 in `test_position_builder_anchor.py`.
  Suite 238/238 gruen.

- **Bug 3 + Bug 4 aus derselben Real-Run-Analyse** in einem Folge-Commit
  zu den ersten vier Fixes:

  - **Bug 3: coord_validator-Errors in Trace + sticky Flag bei
    max_retries** ([src/graph/nodes/planning_nodes.py],
    [src/tools/session_logger.py], [src/graph/state.py]).
    Run e3ddd2d0 hatte 5 ERROR-Issues, die nach `max_retries`
    durchgereicht wurden — der Trace zeigte nur Counts, runs.jsonl
    flagte den Run als success=True. Jetzt traegt der Trace bis zu 50
    formatierte Issue-Zeilen plus `attempts / max_retries /
    unresolved_at_max_retries`. Neue State-Variable
    `coordinate_errors_unresolved` als sticky Flag — bei max_retries
    mit ERRORs wird sie True, der session_logger persistiert sie in
    runs.jsonl. Plus expliziter `node_coordinate_validator_swallowed`
    error-log fuer alerting.
  - **Bug 4: edge_distances + center_offset komponieren additiv**
    ([src/tools/blueprint_resolver.py]). Run e3ddd2d0 tasche_rechts_22
    hatte beide Felder gleichzeitig (`edge_distances={right:25}`
    plus `center_offset={right:10}` aus der Phrase "...25mm entfernt
    10mm nach rechts versetzt"). Resolver-Prioritaet edge>center hat
    den 10mm-Offset stillschweigend verworfen. Neue Semantik:
    edge / pocket_edge legt die Basis pro Achse, center_offset wirkt
    als ADDITIVES Delta on top. Per Achse unabhaengig — Mischformen
    (edge auf X, pure center auf Y) funktionieren weiterhin. 4 neue
    Regression-Tests.

  Tests: +4 splitter-coord-trace, +4 composition. Suite 234/234 gruen.

- **ADR 0004 als Plan fuer Bug 7 + Bug 8** ([docs/decisions/0004-bug7-bug8-anchor-edge-and-splitter-feed.md]).
  Beide Bugs brauchen mehr Vorlauf (LUT + Prompt-Erweiterung fuer
  Bug 7, Pipeline-Edges-Refactor fuer Bug 8) — daher als ADR
  vorbereitet, damit ein neuer Chat sauber einsteigen kann.

- **Vier Bugs aus der Real-Run-Analyse e3ddd2d0 / da35a6ce / e1def0fa**
  behoben. Hintergrund: Run e3ddd2d0 hat ein 16-Tasche-Würfel-Setup
  durchlaufen, da35a6ce + e1def0fa zeigten Phantom-Features auf einer
  extrudierten Platte und verlorene Plattenfeatures. Detail-Analyse
  hat vier saubere Bugs isoliert; alle vier sind jetzt gefixt mit
  Tests. Suite 226/226 gruen.

  - **Bug 5: Splitter `_strip_part_declaration` zerstoert Feature-
    Phrasen ohne Teil-Decl-Praefix** ([src/tools/aktions_splitter.py]).
    Phrasen wie "auf der rechten seite eine nut 10x10 entlang der
    z-achse um 10mm nach rechts versetzt" wurden auf "rechts versetzt"
    reduziert, weil der Strip alles vor dem ersten bare side-keyword
    geworfen hat — auch wenn das Praefix gar keine Teil-Deklaration
    war. Phrasen ohne bare side-keyword wurden komplett gedroppt.
    Fix: nur strippen wenn Praefix ein Part-Keyword (`wuerfel/würfel/
    platte/zylinder/quader/kugel/box/teil/stück`) traegt; Segmente ohne
    bare side-keyword aber mit Feature-Keyword (`tasche/bohrung/nut/
    fase/rundung/...`) bleiben — die Klassifizierer leitet die Seite
    aus Beschreibern wie "rechten seite" ab. 6 neue Regression-Tests.
  - **Bug 6: feature_builder emittiert Phantom-Features fuer Sentinel-
    typs** ([src/tools/feature_builder.py], [src/agents/normalizer_agent.py]).
    Wenn Klassifizierer "unbekannt" und Normalizer "ignorieren" sagen
    (klassisch: Plattendekl-Phrase "vorne soll eine platte hin mit
    140x20x40"), produzierte build_feature einen Default-`hole_single`
    mit Diameter 5 und ID-Praefix "ignorieren_*". Diese Phantom-Bohrung
    landete im Blueprint zentriert auf der Platte. Fix: build_feature
    gibt None zurueck fuer typ in {"", "ignorieren", "unbekannt"};
    define_feature und feature_definierer_node filtern None raus.
    2 neue Regression-Tests in test_normalizer_define_feature.py.
  - **Bug 2: Resolver `_get_child_face_size` liefert child_h=0 fuer
    Pockets auf Side-Faces** ([src/tools/blueprint_resolver.py]).
    pocket_rect-Features tragen `{x, y, depth}` (face-lokal), aber die
    Funktion las cz/cy nach Face-Map, was auf <X/>X/<Y/>Y zu cz=0
    (kein z-Param da) fuehrte. Konsequenz: kante_oben/unten verlor
    die child_half-Subtraktion und verhielt sich wie abstand_*. Run
    e3ddd2d0 tasche_vorne_5 / tasche_links_10 / tasche_rechts_18 alle
    15mm zu hoch (= halbe Pocket-Hoehe). Fix: face-lokale Features
    (Praesenz von `depth` ohne `z`) bekommen (cx, cy) ohne Remapping.
    3-D-Boxes (mit `z`) bleiben beim alten Verhalten. 4 neue Regression-
    Tests in test_kante_vs_abstand.py inkl. Box-Regression.
  - **Bug 1: Klassifizierer-Prompt erkennt "Seite" nicht als Pocket-
    Kante** ([data/prompts/prompt_aktions_klassifizierer.py]). Run
    e3ddd2d0 phrase_idx 2: "die untere Seite von unten 10mm entfernt"
    wurde als `abstand_unten=10` (edge-to-center) klassifiziert statt
    `kante_unten=10` (edge-to-edge). Der Prompt benutzte "Kante" und
    "Seite" inkonsistent — "die obere Kante" triggerte kante_*, "die
    untere Seite" nicht. Fix: System-Prompt explizit erklaert, dass
    "Kante" und "Seite" gleichwertig als Pocket-Edge-Marker zaehlen,
    plus expliziter Few-Shot mit "die untere Seite von unten 10mm".

  Offen aus der Analyse, fuer naechste Iteration:
  - **Bug 7** (Anchor-LUT): "die rechte untere ecke auf der rechten
    kante 10mm nach oben versetzt" mappt `right_edge` auf den Mittel-
    punkt der Kante, nicht auf das untere Ende. Platte landet 100mm
    zu hoch im <Y-Face. Braucht Erweiterung des Anchor-Vokabulars um
    `right_edge_bottom` etc. plus Platzierer-Output.
  - **Bug 8** (Splitter teil_id-Order): wenn der User Plattenfeatures
    VOR der Plattendeklaration schreibt, fallen sie auf den vorigen
    Teil. Two-Pass-Splitting waere strukturell richtiger; vorher steht
    aber der text_splitter / position_extractor zur Korrektur an.
  - **Bug 3** (coord_validator-Logging): die 5 Errors in e3ddd2d0
    sind nur als Counts in den Traces. Issue-Texte sollten in den
    Trace-Output gehen, plus Marker auf success=True wenn ERRORs nach
    max_retries durchgereicht wurden.
  - **Bug 4** (Schema-Composite edge_distances + center_offset):
    feature_definierer setzt beide Felder bei Phrasen wie "...25mm
    entfernt 10mm nach rechts versetzt", Resolver-Prioritaet ignoriert
    center_offset. Schema oder feature_builder muss Composite-Verhalten
    klar definieren (vermutlich: addieren).

## 2026-05-06

- **kante_<dir> Hints fuer explizites edge-to-edge** — User-Direktive
  aus Run df5b92f6: "default: über center bewegt; zusätzlicher Punkt
  wäre Kante zu Kante z.B. 'untere Kante der Tasche von unten 20mm
  entfernt'". Damit hat der Klassifizierer jetzt zwei Hint-Klassen
  fuer die gleiche Achse:

  - `abstand_<dir>` (DEFAULT, edge-to-CENTER): Phrase nennt nur die
    Cube-Kante. "von der rechten Seite 25mm entfernt" → Center 25mm
    von Cube-Right → Pocket-Edge 5mm vom Cube-Edge.
  - `kante_<dir>` (EXPLIZIT, edge-to-EDGE): Phrase nennt BEIDE Kanten —
    die Pocket-Kante UND die Cube-Kante. "die obere Kante der Tasche
    von oben 10mm entfernt" → Pocket-Top-Edge 10mm vom Cube-Top.

  Aenderungen:
  - `data/prompts/prompt_aktions_klassifizierer.py` — System-Prompt
    erklaert beide Konventionen. Existing Few-Shot mit "die obere
    Kante / die linke Seite" Phrasen umgestellt auf `kante_*`. Neuer
    Few-Shot fuer puren `abstand_*`-Fall ("von der rechten Seite 25mm
    entfernt"). Bohrungen bleiben bei abstand_* (point-like).
  - `src/tools/feature_builder.py` — neue `_extract_pocket_edge_distances`
    liest `kante_*` Keys; result landet in
    `feature.position.pocket_edge_distances`.
  - `src/tools/blueprint_resolver.py` — `_compute_offsets` nimmt
    `pocket_edge_distances` als zusaetzlichen Parameter, wendet
    `is_box=True` (child_half-Subtraktion) an. Per-Achse-Prioritaet:
    pocket_edge > edge_distances > center_offset > alignment.
    Mischformen ueber zwei Achsen (z.B. abstand_oben + kante_links)
    werden unterstuetzt. Beide Caller (`_resolve_with_part_frame` und
    `_resolve_feature_in_feature`) passthrough-fertig.

  Tests: neue `tests/tools/test_kante_vs_abstand.py` mit 7 Faellen —
  default abstand_* x2, explizit kante_* x3, Mischform pro Achse,
  Override-Verhalten wenn beides auf derselben Achse. 215/215 Tests
  gruen.

  Hinweis: Bug-1 (coord_validator-False-Positive fuer rotierte
  Pockets) bleibt offen, ist aber kosmetisch nach Bug 2/5-Fix.

- **Bug 5: alle geometrischen Checks raus aus LLM-plan_validator** — Run
  4cebf8ff (selbe Spec wie 3db7d152 mit Bug-2- und Option-B-Fix) hat
  Bug 2 sauber bestaetigt (kein depth-vs-parent-Error mehr) und Bug 4
  geloest (alle 6 rotierten Taschen mit korrekten edge_distances), aber
  eine NEUE Klasse von false positives gezeigt: der LLM hat
  "Check 10: placement.offset_y=100 exceeds parent pocket dimension"
  gemeldet — fuer Bohrungen die per coord_validator-Check (deterministisch)
  korrekt platziert sind. Die Pruefung hat in der Prompt-Checkliste gar
  keine Nummer 10 fuer Offset-Bounds; der LLM hat sie sich ausgedacht.

  Selbe Wurzel wie Bug 2: das LLM macht geometrische / numerische
  Mathe unzuverlaessig. Architektur-richtig: alle solchen Checks
  gehoeren in den deterministischen `coordinate_validator`, der
  Frame-Transformationen (Pocket-lokal, rotated) korrekt kann.

  Prompt-Refactor:
  - Neuer "ABSOLUT VERBOTEN"-Block am Anfang: keine Zahlen-Vergleiche,
    kein "exceeds parent", kein Position/Offset/Bounds-Check, kein
    Wandstaerke-/Lochkreis-/Pattern-Spacing-Check, keine
    Tiefen/Hoehen-Vergleiche.
  - Alte Rules 5, 7, 8 entfernt (Maße>0, Lochkreis, Wandstaerke) —
    coord_validator macht alle drei deterministisch (Checks 6, 4, 5).
  - Verbleibend: 9 strukturelle / semantische Rules: parent=null root,
    unique IDs, parent-Existenz, build_order-Vollstaendigkeit,
    placement/face/selector-Praesenz, Spec-Coverage,
    Spec-Mass-Konsistenz.
  - Token-Budget von ~1800 auf ~1700 gesunken; Aufgabe ist jetzt klar
    abgegrenzt.

- **Option B: Klassifizierer extrahiert edge_distances + center_offsets**
  (Stufe-5c-Iteration auf ADR 0003) — der Klassifizierer-Prompt
  erweitert um `abstand_<seite>` (Kantenabstaende nach innen) und
  `versatz_<seite>` (Mittenversatz) als parameter_hints. Vier neue
  Few-Shots: edge-distances, center-offsets, gemischt mit Rotation,
  und ein nested-Bohrung-Beispiel mit edge-distances in der Tasche.

  Lastverteilung neu: Normalizer-Aufgabe schrumpft auf
  position-keyword + richtung + Edge-Selector — typ/seite/Mass-Hints
  liefert der Klassifizierer alle. Die Normalizer-Faelligkeit aus
  Run 3db7d152 (Bug 4: rotierte Tasche + edge_distances → ein Wert
  auf 0 verloren) wird damit umgangen.

  `_merge_param_hints` Semantik geaendert: Klassifizierer-Hints
  gewinnen jetzt ueber Normalizer-Parses (vorher: Normalizer wins).
  Begruendung: der Klassifizierer hat einen kleineren Prompt mit
  klarer Anleitung pro Hint-Typ und sieht nur die eine Phrase; der
  Normalizer mit think=false durch den 329-Zeilen-Mega-Prompt fehlt
  bei kniffligen Faellen sub-perfekt. Wenn der Klassifizierer einen
  Wert explizit emittiert, ist das die zuverlaessigere Quelle.

  Tests aktualisiert: `test_classifier_hints_override_normalizer_parses`
  ersetzt das alte `test_hints_do_not_override`. Plus
  `test_classifier_hint_overrides_normalizer_zero_value` als
  Regression fuer Bug 4. 208/208 Tests gruen.

- **Bug 2: depth-vs-parent-Check raus aus LLM-plan_validator** —
  Check 6 ("Feature kleiner als sein Parent?") aus
  [data/prompts/prompt_plan_validator.py] entfernt; der LLM bekommt
  jetzt explizit gesagt, dass diese Pruefung der deterministische
  `coordinate_validator` macht (Check 2 / `depth_vs_material`,
  feature-in-feature wird ueber `_resolve_root_parent_id` korrekt
  gegen die Root-Part-Hoehe geprueft, nicht gegen die Pocket-Tiefe).
  Damit entfaellt auch der Regex-Post-Filter aus ADR 0002 — die
  Filter-Funktion `_drop_pocket_floor_depth_errors` plus
  `_has_blocking_errors` sind aus [src/agents/plan_validator.py] raus,
  ebenso die jetzt obsolete Test-Datei
  `tests/agents/test_plan_validator_pocket_floor.py`.
  ADR 0002 als superseded markiert.

  Hintergrund: Run 3db7d152 hat den Regex-Filter aus ADR 0002 versagen
  sehen — der LLM hat 7 von 8 nested Bohrungen als depth-violation
  gemeldet, aber das Format der Fehlermeldung hat die Filter-Regex
  nicht gematcht. Architektur-richtige Loesung: Mathe-Check gehoert in
  den deterministischen Validator, nicht in den LLM-Prompt.

  -83 Zeilen Code, -1 Test-Datei. 207/207 Tests gruen.

- **Quick Wins fuer Stufe 5c** — zwei kleine Aenderungen aus der
  Real-Run-Analyse von Run 3c0212ae:
  - `agent_options.normalizer.think=false` (config.yaml). Im neuen Pfad
    hat der Aktions-Klassifizierer (Stufe 2) typ/seite/parameter_hints
    bereits extrahiert; der Normalizer parst nur noch position/richtung
    /Versatz-Details. Reasoning ist da Overkill und kostet 8-16s/Call.
    Erwarteter Effekt: feature_definierer-Latenz von ~16s/Call auf
    2-4s/Call.
  - Klassifizierer-Prompt um Rotations-Vorzeichen-Konvention erweitert:
    "im Uhrzeigersinn" → negativ, "gegen Uhrzeigersinn" → positiv
    (CadQuery-CCW-positiv-Konvention). Plus zwei neue Few-Shot-
    Beispiele die genau diese Faelle zeigen. Run 3c0212ae hatte 4 von
    8 rotierten Taschen mit falschem Vorzeichen (alle "im
    Uhrzeigersinn"-Faelle wurden als +20 statt -20 klassifiziert).

- **Pipeline-Verdrahtung (Stufe 5b von ADR 0003)** — die in Stufe 5a
  vorbereiteten Per-Aktion-Nodes sind jetzt im LangGraph aktiv.
  Aenderungen am Graph:
  - `inventar_node` ruft auf fresh runs `extract_teile_only()` (Step A
    only). Retry-Pfad mit validator_feedback bleibt auf legacy
    `extract()` damit Teil-Dimensions-Korrektur weiter funktioniert.
  - Neue Edges: `inventar → aktions_splitter → aktions_klassifizierer
    → text_splitter → position_extractor → feature_definierer →
    aktions_aggregator → platzierer`. Damit ersetzt die deterministische
    Splitter+Klassifizierer-Kombi den verklumpenden Inventar-Step-B.
  - `feature_definierer_node` umgestellt auf
    `NormalizerAgent.define_feature(klass, teil)`. Eingabe sind die
    `aktions_klassifikationen` aus Stufe 2; Ausgabe sind `aktions_features`
    mit `_teil_id / _phrase_idx / _parent_phrase_idx`-Markern. Ueberlebt
    einzelne Klassifikationen ohne Teil-Zuordnung mit Warning.
  - `aktions_aggregator_node` ist jetzt der Producer von
    `teil_definitionen` (deterministisch). Nested Bohrung-in-Tasche
    bekommt parent=tasche_id ohne dass `pocket_child_placer` noch das
    LLM bemuehen muesste — der bleibt aber als Sicherheitsnetz im Graph.
  - Initial-State init in pipeline.py um die neuen Felder ergaenzt.
  - Modify/Error-Loop-Pfad ueber `blueprint_architect` ist unangetastet.
  - Graph compiliert sauber (27 Nodes, +3 ggue. Stufe 5a). Suite weiter
    217/217 gruen. Real-Run-Verifikation (Stufe 5c / ADR Stufe 6) folgt
    separat — dort wird auch `agent_options.normalizer.think=false`
    gegen die Latenz pruefen.

- **Pipeline-Vorarbeit (Stufe 5a von ADR 0003)** — alles additiv, noch
  kein Graph-Wiring. Vorbereitet:
  - `InventarAgent.extract_teile_only(specification)` liefert die Step-A-
    Teile-Liste OHNE den verklumpenden Step B (aktionen=[] explizit).
    Die alte `extract()` bleibt fuer Modify/Error-Loop-Pfad unangetastet.
  - PipelineState bekommt drei neue Felder:
    `aktions_phrases`, `aktions_klassifikationen`, `aktions_features`.
  - Drei neue Node-Wrapper in [src/graph/nodes/planning_nodes.py]:
    `aktions_splitter_node` (deterministisch), `aktions_klassifizierer_node`
    (LLM-Loop), `aktions_aggregator_node` (deterministisch). Alle drei
    emittieren agent_traces und sind ueber `src.graph.nodes` exportiert.
    NOCH NICHT in den Graph eingehaengt — Stufe 5b verdrahtet.
  - Klassifizierer-Node reicht parent_phrase fuer nested Children durch
    (so dass Stufe 2 die seite vom Parent erben kann), ueberlebt einzelne
    classify-Exceptions ohne den Loop abzubrechen.
  - 11 Node-Tests + 4 Tests fuer extract_teile_only — alle gruen.
  - Suite weiterhin 217/217 gruen.

- **Aktions-Aggregator (Stufe 4 von ADR 0003)** — neuer deterministischer
  Modul `src/tools/aktions_aggregator.py`. `aggregate(features, teile)`
  baut die finale `teil_definitionen[]`-Struktur aus den Pro-Aktion-
  Features von `define_feature` (Stufe 3). Gruppiert nach `_teil_id`,
  sortiert per `_phrase_idx` (Spec-Reihenfolge), loest `_parent_phrase_idx`
  in die Parent-Feature-ID auf (das fixt deterministisch den
  Verschachtelungs-Pfad: Bohrung in Tasche kriegt jetzt `parent=tasche_*`
  statt `parent=teil_id`). Strippt interne Marker im Output, damit das
  Schema 1:1 zum heutigen `build_teil_definition`-Output passt.
  Orientation aus `teil.beschreibung` (gleiche Heuristik wie heute:
  hochkant / flach / standard). Dangling parent_phrase_idx faellt auf
  `teil_id` zurueck und loggt. 16 Unit-Tests gruen. End-to-End-Smoke der
  ganzen Stufe 1+2+3+4-Kette auf 2 Tasche+Bohrung-Paaren liefert eine
  korrekte `teil_definitionen[]` mit aufgeloesten parent-Verweisen.
  Standalone-Modul — Pipeline-Wiring folgt in Stufe 5.

  Nebenaenderung in [src/agents/normalizer_agent.py]: `define_feature`
  setzt jetzt zusaetzlich den `_teil_id`-Marker, damit der Aggregator
  features auch nach parent-Rewrite korrekt gruppieren kann.

- **Toten Test-Code entfernt** — 4 Test-Files mit collect-errors auf
  geloeschte Module raus (`test_planner_diff.py`, `test_prompt_assembler.py`,
  `test_feature_tagger.py`, `tests/graph/` komplett — der conftest dort
  importierte 3 nicht mehr existierende Agents). Plus 7 stale Tests in
  `test_config.py` (referenzierten `models.planner_*`) und 1 Assert in
  `test_function_decomposer.py` (testete altes code_skeleton-Verhalten).
  Vorher: 10 fail / 13 collect-error. Jetzt: 202/202 gruen (ohne
  tests/golden/ — Ollama — und tests/test_app.py — eigener Bug
  `SessionState.last_run_id`).

- **feature_definierer-Refactor (Stufe 3 von ADR 0003)** — neue Methode
  `NormalizerAgent.define_feature(klassifikation, teil)` als Pro-Aktion-
  Eintrittspunkt. Eingabe: 1 klassifizierte Aktion (vom Aktions-
  Klassifizierer aus Stufe 2). Ausgabe: 1 SemanticFeature gemaess ADR-
  Schnittstellen-Vertrag, inklusive `_phrase_idx` und `_parent_phrase_idx`-
  Marker fuer den Aggregator (Stufe 4). `parent` defaultet auf die
  teil_id; der Aggregator ueberschreibt fuer nested Children (Bohrung in
  Tasche) mit der Pocket-Feature-ID. Type-Reconciliation respektiert
  Familien (Classifier `bohrung` + Normalizer `lochkreis` → Normalizer
  gewinnt; cross-family oder Normalizer `ignorieren` → Classifier
  gewinnt). Classifier-Seite trumpft Normalizer-Seite (Stufe 2 hat sie
  schon validiert / vom Parent geerbt). Hints aus Stufe 2 fuellen Luecken
  in `parameter` (rotation_deg → drehung Translation), ueberschreiben
  aber nicht was der Normalizer geparst hat. 17 Unit-Tests gruen.
  Live-Smoke (Splitter → Klassifizierer → define_feature) auf 2 nested
  Tasche+Bohrung-Paare laeuft strukturell korrekt, aber zeigt das alte
  Latenz-Problem: Normalizer mit Default `think=true` braucht ~60s/Call.
  Stufe 5 entscheidet ob `agent_options.normalizer.think=false` machbar
  ist (Aufgabe ist mit Pre-Klassifikation deutlich kleiner). Existing
  `normalize()` API bleibt unveraendert — Stufe 5 schaltet das Call-
  Site um.

- **Aktions-Klassifizierer (Stufe 2 von ADR 0003)** — neuer Agent
  `src/agents/aktions_klassifizierer.py` klassifiziert genau EINE Phrase
  vom Splitter in `{typ, seite, parameter_hints}`. Strukturelle Felder
  vom Splitter (`teil_id`, `phrase_idx`, `parent_phrase_idx`) werden 1:1
  durchgereicht; das LLM klassifiziert nur. Modell `gemma4:26b` mit
  `think=false`, `temperature=0.0` — Aufgabe ist trivial (5 Typen).
  Robust gegen defekte LLM-Outputs (unbekannter Typ → `"unbekannt"`,
  unbekannte Seite → `"oben"`, kaputtes parameter_hints → leeres Dict,
  LLM-Exception → Default-Klassifikation mit erhaltenen Splitter-Feldern).
  13 Unit-Tests gruen. agent_contracts.py-Adapter und config-Eintrag
  ergaenzt; aktiv geschaltet wird der Contract erst in Stufe 7
  (DSPy-Re-Training). Standalone — Pipeline-Integration in Stufe 5.

- **Aktions-Splitter (Stufe 1 von ADR 0003)** — neuer deterministischer
  Modul `src/tools/aktions_splitter.py` segmentiert die User-Spec in
  einzelne Aktions-Phrasen. Splittet an Komma, Seiten-Schluesselwoertern
  und Verschachtelungs-Markern (`in der Tasche`, `in der Ausnehmung`,
  `darin`, `innerhalb`). Verschachtelte Aktionen ("Bohrung in der
  Tasche") bekommen `parent_phrase_idx` gesetzt — der Verschachtelungs-
  Bug aus Run 6efaa489 (3 statt 6 Aktionen) und 14fa8d40 (16 statt 24)
  ist damit deterministisch geloest. 17 Tests gruen, davon 3 Reference-
  Runs aus dem ADR. Noch nicht in die Pipeline verdrahtet — Standalone-
  Modul, integriert wird in Stufe 5. Siehe
  [ADR 0003](docs/decisions/0003-inventar-feature-definierer-pro-aktion.md).

## 2026-05-05

- **plan_validator filtert pocket_floor depth-Errors deterministisch**
  (`ca15719`) — Check 6 hat false positives fuer Bohrungen produziert, die
  absichtlich durch den Taschenboden ins Material gehen. Der LLM-Validator
  hatte das nicht verstanden und einen vollen Retry-Cycle (~17s) ausgeloest.
  Loesung: Post-Filter wirft Errors raus, wenn das betroffene Feature
  `params.depth_reference_applied="pocket_floor"` traegt. Siehe
  [ADR 0002](docs/decisions/0002-plan-validator-pocket-floor-filter.md).

- **pocket_child_placer reicht Position vom feature_definierer durch**
  (`9393767`) — Bisher hat der Agent das LLM zweimal Position parsen lassen
  und dabei Versatz-Werte verloren (Run 965da548: "10mm nach oben"-Versatz
  ging verloren). Jetzt macht er nur noch Containment-Mapping (welche
  Bohrung in welche Tasche), die Position kommt 1:1 vom Upstream-Feature.
  Latenz 21s -> 6.4s. Siehe
  [ADR 0001](docs/decisions/0001-pocket-child-placer-mapping-only.md).

## 2026-05-04

- **per-Teil Labeler + Anker/Edge-Distanz Trainings-Cases** (`7eb3b93`) —
  position_extractor ist umgebaut zum per-Teil Labeler (placement vs feature),
  21 Trainings-Cases in `data/dspy_training/labeler_platzierer_traces.py`,
  `_parse_kv` akkumuliert Multi-Line-Keys.

- **consolidate pending in-flight work** (`5c4cf4b`) — Sammel-Commit
  fuer kleinere konsolidierte Aenderungen.

## 2026-05-03

- **rewrite 'Zur Entstehung' in personal voice** (`674975c`) — README-Sektion
  ueberarbeitet.

- **split function_decomposer into focused modules** (`57d97a0`) — Refactor:
  function_decomposer in fokussierte Untermodule zerlegt.

## 2026-05-01

- **prevent Coder-Crash on simple specs + train Inventar 'auf X-Seite' pattern**
  (`cc3ca86`) — Coder-Crash bei Simple-Specs verhindert, Inventar mit neuem
  Trainings-Pattern.

- **stable workplane origin via _ref-pattern (Centroid-Drift-Bug)**
  (`22f6ef0`) — Workplane-Origin stabilisiert.

- **alignment-upgrade darf edge_distances nicht ueberschreiben** (`a527ee1`)
  — Alignment-Upgrade-Logik korrigiert.

## 2026-04-30

- **wire DSPy-optimized demos into pipeline agents** (`ad5ce37`) — DSPy-
  optimierte Demos in Pipeline-Agents eingebunden.

- **align DSPy training targets with pipeline reality** (`863309d`) —
  Trainings-Targets an Pipeline-Realitaet ausgerichtet.

## 2026-04-28

- **DSPy training adapter for local LLMs** (`a3016f1`) —
  DSPy-Trainings-Adapter fuer lokale LLMs (think=False + JSONAdapter).

## Aelter

Fuer Aenderungen vor diesem Punkt siehe `git log` direkt.
