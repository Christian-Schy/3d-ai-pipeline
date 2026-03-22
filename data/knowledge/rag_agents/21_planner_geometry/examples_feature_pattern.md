# Examples: Patterns (Lochbilder, Raster, Lochkreis)
Tags: pattern, hole_pattern, grid, circular, bolt_circle, array, repeat, holes, raster

## Beispiel 1: 2x2 Ecklöcher mit Randabstand
Spezifikation: "Platte 100x80x10mm, 4 Löcher ∅8mm in den Ecken, Randabstand 12mm"

```json
{
  "description": "Platte 100x80x10mm mit 4 Ecklöchern ∅8mm (Randabstand 12mm)",
  "build_order": ["base", "corner_holes"],
  "features": {
    "base": {
      "type": "box",
      "params": {"x": 100.0, "y": 80.0, "z": 10.0},
      "parent": null,
      "placement": null,
      "notes": ""
    },
    "corner_holes": {
      "type": "hole_pattern_grid",
      "params": {
        "x_count": 2,
        "y_count": 2,
        "x_spacing": 76.0,
        "y_spacing": 56.0,
        "diameter": 8.0,
        "depth": null
      },
      "parent": "base",
      "placement": {
        "face": ">Z",
        "position": "center",
        "offset_x": 0.0,
        "offset_y": 0.0
      },
      "notes": "x_spacing=100-2*12=76, y_spacing=80-2*12=56; depth=null → durch"
    }
  }
}
```

## Beispiel 2: 3x4 Lochraster gleichmäßig verteilt
Spezifikation: "Platte 120x90x8mm, 3x4 Lochraster ∅6mm, Abstand 30mm"

```json
{
  "description": "Platte 120x90x8mm mit 3x4 Lochraster ∅6mm, Rasterabstand 30mm",
  "build_order": ["base", "hole_grid"],
  "features": {
    "base": {
      "type": "box",
      "params": {"x": 120.0, "y": 90.0, "z": 8.0},
      "parent": null,
      "placement": null,
      "notes": ""
    },
    "hole_grid": {
      "type": "hole_pattern_grid",
      "params": {
        "x_count": 3,
        "y_count": 4,
        "x_spacing": 30.0,
        "y_spacing": 30.0,
        "diameter": 6.0,
        "depth": null
      },
      "parent": "base",
      "placement": {
        "face": ">Z",
        "position": "center",
        "offset_x": 0.0,
        "offset_y": 0.0
      },
      "notes": "Rasterbreite X: (3-1)*30=60mm, Y: (4-1)*30=90mm; zentriert auf Platte"
    }
  }
}
```

## Beispiel 3: Lochkreis (Bolt Circle)
Spezifikation: "Runde Platte ∅100mm, 6mm dick, 6 Löcher ∅8mm auf Lochkreis ∅70mm"

```json
{
  "description": "Runde Platte ∅100mm H6mm mit 6 Löchern ∅8mm auf Lochkreis ∅70mm",
  "build_order": ["base", "bolt_circle"],
  "features": {
    "base": {
      "type": "cylinder",
      "params": {"diameter": 100.0, "height": 6.0},
      "parent": null,
      "placement": null,
      "notes": ""
    },
    "bolt_circle": {
      "type": "hole_pattern_circular",
      "params": {
        "circle_diameter": 70.0,
        "n_holes": 6,
        "diameter": 8.0,
        "depth": null
      },
      "parent": "base",
      "placement": {
        "face": ">Z",
        "position": "center",
        "offset_x": 0.0,
        "offset_y": 0.0
      },
      "notes": "Lochkreis ∅70mm, 6 Löcher gleichmäßig; check: 35+4=39 < 50 ✓"
    }
  }
}
```

## Beispiel 4: Steg mit Lochkreis auf Basis
Spezifikation: "Flansch: Basis ∅120mm H12mm, Steg ∅60mm H20mm zentral, 4 Löcher ∅10mm auf LK ∅90mm"

```json
{
  "description": "Flansch ∅120mm H12mm mit Steg ∅60mm H20mm + 4 Löcher LK∅90mm",
  "build_order": ["base_flange", "bolt_holes", "center_boss"],
  "features": {
    "base_flange": {
      "type": "cylinder",
      "params": {"diameter": 120.0, "height": 12.0},
      "parent": null,
      "placement": null,
      "notes": ""
    },
    "bolt_holes": {
      "type": "hole_pattern_circular",
      "params": {
        "circle_diameter": 90.0,
        "n_holes": 4,
        "diameter": 10.0,
        "depth": null
      },
      "parent": "base_flange",
      "placement": {
        "face": ">Z",
        "position": "center",
        "offset_x": 0.0,
        "offset_y": 0.0
      },
      "notes": "Bohrungen VOR Union des Stegs (Boolean-Reihenfolge!)"
    },
    "center_boss": {
      "type": "cylinder",
      "params": {"diameter": 60.0, "height": 20.0},
      "parent": "base_flange",
      "placement": {
        "face": "NearestToPoint",
        "selector_point": [0.0, 0.0, 12.0],
        "position": "center",
        "offset_x": 0.0,
        "offset_y": 0.0
      },
      "notes": "Steg (Union) NACH Bohrungen; NearestToPoint nach Union"
    }
  }
}
```
