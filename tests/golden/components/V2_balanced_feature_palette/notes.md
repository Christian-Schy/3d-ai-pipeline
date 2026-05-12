# V2 Balanced Feature Palette

Status: `baseline_green`

Second clean variation set for the supported standard path. It intentionally
mixes feature families in one task, but keeps every expected behavior inside
the current deterministic schema/template vocabulary.

Covered:
- holes: centered, corner edge distances, edge distance plus center offset
- pockets: edge-to-edge, center offset, rotation, "hoehe" as depth
- slots: x/y/z axis wording, explicit length, through/full-length omission,
  edge distance, center offset, rotation via axis angle
- patterns: lochkreis, 2x2 grid, linear row along z
- feature-on-additive-part: hole, pocket and slot on `platte`

Real-smoke status:
- `scripts.run_real_goldens --filter V2 --first-only --no-persist --no-jsonl`
  passes 1/1 on the current local setup.

Intentionally not covered as expected:
- linear-pattern `start_offset`: schema/resolver preserve it, but the current
  `hole_pattern_linear` template does not yet use it for geometry placement.
- counterbore/countersink: codegen templates exist, but the Normalizer
  training adapter still treats them as unsupported for standard training.
- edge features/modifiers: classifier and normalizer seeds exist for
  fase/rundung wording, and modifier templates accept the assembler call
  signature. The dense V2 expected set still omits them because selector and
  executor behavior is not robust enough for a clean end-to-end golden.
