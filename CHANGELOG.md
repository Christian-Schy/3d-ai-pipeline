# Changelog

Chronologische Liste nennenswerter Aenderungen am Projekt. Pro Eintrag der
Commit-Hash, eine Kurzbeschreibung und (wenn vorhanden) ein Verweis auf die
zugehoerige ADR unter `docs/decisions/`.

Architektur-Entscheidungen liegen als ADRs (Architecture Decision Records)
in `docs/decisions/` — dort steht das **Warum** zu jeder grundlegenden
Aenderung. Hier in der Changelog steht das **Was** mit Datum.

## 2026-05-10

- **Baseline-Hygiene fuer komplexe Standard-Teile gestartet.**
  Pipeline-Goldens sind als `slow` markiert und werden per Default nicht
  von `pytest` gestartet; Component-Goldens bleiben schnell. Config nimmt
  `models.aktions_klassifizierer` jetzt explizit an, UI-History-Testdrift
  wurde auf die aktuelle Restore-Outputliste synchronisiert, und ein
  gemeinsames Run-Success-Gate verhindert, dass STL-only/leer-Blueprint
  oder unresolved-coordinate Runs als Erfolg in UI/API/Logs erscheinen.
  Die Golden-Doku beschreibt nun die Capability Ladder von Einzel-Features
  bis grossen Kombi-Teilen samt Heatmap-Kommandos.

## 2026-05-08

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
