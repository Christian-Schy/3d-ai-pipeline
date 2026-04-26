# Golden Case: platte_hochkant_p2_bohrung

**Quelle:** Trace `t27_platte_hochkant_oben_p2_bohrung_ta` aus sonnet_traces.py
**Difficulty:** P2
**Category:** single_part_single_feature
**Sprachstil:** technisch_ausfuehrlich

## Was wird hier getestet?

hochkant-Orientation-Swap: Y/Z getauscht, Bohrung auf neuer Oberseite (120x15), P2 Eck-Abstand

## Assertions aus Trace

```json
{
  "expected_bbox": [
    120,
    15,
    90
  ],
  "expected_feature_count": {
    "box": 1,
    "hole_single": 1
  }
}
```

## Bekannte Risiken

<!-- Eintragen wenn der Test rot wird -->
