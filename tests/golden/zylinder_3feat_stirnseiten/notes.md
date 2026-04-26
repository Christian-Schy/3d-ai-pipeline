# Golden Case: zylinder_3feat_stirnseiten

**Quelle:** Trace `t67_zylinder_3features_stirnseiten_umg` aus sonnet_traces.py
**Difficulty:** P0
**Category:** single_part_multi_feature
**Sprachstil:** umgangssprachlich

## Was wird hier getestet?

Zylinder Stirnseite oben+unten, multi-feature: 2 Bohrungen + 1 Tasche — Stirnflächen-Mapping

## Assertions aus Trace

```json
{
  "expected_feature_count": {
    "cylinder": 1,
    "hole_single": 2,
    "hole_pattern_circular": 1
  }
}
```

## Bekannte Risiken

<!-- Eintragen wenn der Test rot wird -->
