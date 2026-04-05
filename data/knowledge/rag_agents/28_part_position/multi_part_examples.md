# Multi-Part Positionierung — Mehrere Teile auf einer Basis
Tags: multi, teil, platte, aufsatz, mehrere, zwei, position, stacked, nebeneinander

## Zwei Platten auf einer Basis

### Beispiel: Rechts und Links
Spec: "Basis 100×100×20. Platte rechts 20×80×40, bündig rechts. Platte links 20×80×40, bündig links."

```json
{
  "positions": {
    "plate_right": {
      "face": ">Z",
      "alignment": "flush_right",
      "orientation_hint": null
    },
    "plate_left": {
      "face": ">Z",
      "alignment": "flush_left",
      "orientation_hint": null
    }
  }
}
```

### Beispiel: Vorne und Hinten
Spec: "Basis 120×80×10. Wand hinten 120×10×50, bündig hinten. Wand vorne 120×10×50, bündig vorne."

```json
{
  "positions": {
    "wall_back": {
      "face": ">Z",
      "alignment": "flush_top",
      "orientation_hint": null
    },
    "wall_front": {
      "face": ">Z",
      "alignment": "flush_bottom",
      "orientation_hint": null
    }
  }
}
```

## Teile übereinander (Stacking)

### Beispiel: Platte auf Platte
Spec: "Basis 100×100×20. Platte oben 80×80×10, zentriert. Deckel oben auf Platte 60×60×5, zentriert."

```json
{
  "positions": {
    "plate_mid": {
      "face": ">Z",
      "alignment": "centered",
      "orientation_hint": null
    },
    "cover_top": {
      "face": ">Z",
      "alignment": "centered",
      "orientation_hint": null
    }
  }
}
```
Hinweis: cover_top hat parent=plate_mid (nicht base!) — das bestimmt der Feature Assigner.

## Teil mit Abstand (schwebend)

### Beispiel: Deckel 10mm über Basis
Spec: "Basis 50×50×20. Deckel 50×50×5, 10mm über der Basis schwebend."

```json
{
  "positions": {
    "cover": {
      "face": ">Z",
      "alignment": "centered",
      "distance_mm": 10.0,
      "orientation_hint": null
    }
  }
}
```

## Teile mit horizontalem Abstand

### Beispiel: Stütze mit Abstand vom Rand
Spec: "Basis 100×100×20. Stütze 20×20×40, 10mm vom rechten Rand."

```json
{
  "positions": {
    "support": {
      "face": ">Z",
      "alignment": "flush_right",
      "gap_mm": 10.0,
      "orientation_hint": null
    }
  }
}
```

## WICHTIG: Jedes Teil hat GENAU EINEN Parent

- Teil sitzt auf Basis -> parent = base (Feature Assigner bestimmt das)
- Teil sitzt auf anderem Teil -> parent = dieses andere Teil
- Part Position Assigner bestimmt NUR wo auf dem Parent, NICHT wer der Parent ist!
