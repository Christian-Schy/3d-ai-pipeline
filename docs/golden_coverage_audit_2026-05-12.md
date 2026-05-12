# Golden Coverage Audit 2026-05-12

Scope: current component/pipeline goldens plus DSPy seed/training data after
the 2026-05-12 21:44 heatmap and the added V2 balanced palette.

Policy note: failing real-run goldens are valid when they are marked as
`target_should_work` or `known_gap`. They should stay in the heatmap to expose
missing layers. What must stay clean is the expected data itself: resolver
expected files and positive DSPy seeds must describe the intended contract,
not the current broken output.

Latest heatmap inspected: `data/sessions/heatmap_20260512_214436.md`.

Result:
- 17 real golden specs total: 15 pass, 2 fail.
- Remaining fails:
  - `M_kombo_basics`: at inspection time, `feature_definierer` dropped
    `start_offset` and `direction` for the anchored linear hole row.
    Direction preservation now has a deterministic fallback and V2 coverage;
    `start_offset` remains the unsupported part.
  - `E_kombo_basics`: pipeline-level parent cycle for one generated plate.
- Post-audit V2 smoke: `scripts.run_real_goldens --filter V2 --first-only`
  passes 1/1 after keeping the expected set inside supported behavior.

## Inventory

Component resolver goldens now cover these feature families:

| Scope | Feature types | Sides | Positioning |
|---|---|---|---|
| B1/B2/B3/B_kombo* | `hole_single` | oben, rechts | center offset, edge distances, anchor |
| M_kombo | circular/grid/linear hole patterns | oben, rechts | centered, center offset, anchor, edge-distance drop for grids |
| N_kombo | `slot` | oben, rechts | centered, edge distances, center offset, anchor, rotation |
| T_kombo | `pocket_rect` | oben, rechts | centered, edge distances, pocket edge-to-edge, center offset, anchor, rotation |
| EF_kombo | features on additive plate | oben, unten | hole, pocket, slot on child part |
| NEST_kombo | feature-in-feature | oben | hole-in-pocket, rotated pocket frames |
| V2 palette | mixed supported families | oben, unten, rechts, vorne | holes, pockets, slots, patterns, features on additive plate |

DSPy data after V2 additions:

| Agent/data source | Count | Coverage notes |
|---|---:|---|
| `klassifizierer_traces.py` | 111 | all six sides present, still top-heavy by design because most CAD examples target top faces |
| `hole_classifier` seed projection | 28 | centered, corners, edge distance, center offset, side faces |
| `pocket_classifier` seed projection | 32 | edge-to-edge, center offset, rotation, `hoehe` as depth |
| `slot_classifier` seed projection | 24 | x/y/z axes, with/without length, edge distance, center offset, rotation |
| `pattern_classifier` seed projection | 17 | lochkreis/teilkreis, 2x2 grid, side-face grid, linear rows |
| `edge_feature_classifier` seed projection | 10 | fase/rundung wording, top/vertical edge language |
| `normalizer_traces.py` | 60 | runtime shortform for all standard families and all six sides |
| `variation_traces.py` | 8 | first language-variation pack only; V2 uses direct seeds + component goldens |

## Coverage Matrix

| Feature family | Sides | Local directions / edges | Position types | Language variants | Training agents |
|---|---|---|---|---|---|
| Bohrung | oben, unten, rechts, links, vorne, hinten | top/bottom/right/left/front/back via `abstand_*` and `versatz_*` | centered, corner, edge-distance, center-offset, mixed edge+offset, anchor | "von Kante", "jeweils von den Kanten", "aus Mitte", reordered phrase | splitter, hole_classifier, normalizer, resolver |
| Tasche | oben, unten, rechts, links, vorne | top/bottom/right/left/front/back via `kante_*`, `abstand_*`, `versatz_*` | centered, edge-to-edge, center offset, mixed, rotation | "deren X Kante", "Hoehe" as depth, clockwise/ccw | pocket_classifier, normalizer, resolver |
| Nut | oben, unten, rechts, links, vorne, hinten in training; resolver goldens mainly oben/rechts/vorne | x/y/z according to face; edge and center offsets | centered, full-length omission, explicit length, edge distance, center offset, rotation, flush edge | "entlang x/y/z", "liegt auf rechter Kante an", AxB plus explicit length | slot_classifier, normalizer, resolver |
| Pattern | oben/rechts/vorne in current goldens; training also broader | x/y/z linear rows; grid inset; circular center offset | centered, center offset, grid inset, linear spacing | lochkreis, teilkreis, lochmuster 2x2, bohrungsreihe/lochreihe | pattern_classifier, normalizer, resolver |
| Kantenfeatures | top and vertical wording in seed data | `kanten=alle_oberen`, `kanten=vertikal`; deterministic selector contract still coarse | modify-only, no placement math dependency | fase, rundung, abrunden/kantenradius variants | edge_feature_classifier, normalizer |
| Additive/features-on-additive | oben/rechts/vorne in E/EF plus V2 plate | child part faces | centered, anchor, rotation, child features on plate | "auf der Platte oben ..." | splitter, placement agents, normalizer, resolver |

## Gaps

- Full six-face component resolver coverage is still uneven. Holes have the
  best six-side training coverage; pockets and slots still need more resolver
  goldens on `links`, `hinten`, and `unten`.
- Local direction semantics on side faces are covered in training, but not yet
  balanced in resolver goldens. V2 adds `unten`, `rechts`, and `vorne`; `links`
  and `hinten` remain next candidates.
- Linear-pattern `start_offset` is only partially supported. Schema and
  resolver preserve it, and current M_kombo expects it, but the codegen
  template does not yet place row holes from `start_offset`. V2 therefore does
  not train it as a clean expected case.
- Counterbore/countersink are intentionally absent from Normalizer training.
  Templates exist, but the current training adapter marks them unsupported.
- Edge-feature end-to-end coverage is intentionally held out of the V2
  expected set. `alle_oberen` and `vertikal` are represented in training, and
  modifier templates now match the assembler call signature, but selector and
  executor behavior still need hardening before broad golden expansion.
- The top face remains overrepresented. This is realistic for early CAD tasks
  but should be corrected gradually with side-face component goldens instead
  of flooding the seed data.
- Complex target tasks should be added as target/gap goldens even before they
  are fully green, as long as `notes.md` marks the status and training seeds
  are only added for already-correct agent-local contracts.

## V2 Set

Added `tests/golden/components/V2_balanced_feature_palette/`:

- `resolver/`: deterministic mixed-feature resolver golden.
- `splitter/`: action phrase segmentation golden with `wuerfel` and `platte`.
- `pipeline/specs.txt`: one dense real-run spec for future filtered heatmaps.
- `notes.md`: support boundary and intentional omissions.
- Filtered real smoke: 1 PASS / 0 FAIL. The spec exports an STL and reaches
  validator success; mesh validation reports only a minimal tessellation
  warning.

Added matching direct seeds:

- `data/dspy_training/klassifizierer_traces.py`: 13 V2 phrase-level classifier
  examples distributed over hole, pocket, slot, and pattern sub-agents.
- `data/dspy_training/normalizer_traces.py`: 13 V2 runtime-shortform examples.

No unsupported features were added as expected training targets.
