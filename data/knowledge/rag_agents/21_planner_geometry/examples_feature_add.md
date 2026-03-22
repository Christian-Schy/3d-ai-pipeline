# Examples: Feature Add (Stege, Bosses, Rippen auf Basis)
Tags: boss, rib, pad, steg, protrusion, add, extrusion, raised, feature_add

## Beispiel 1: Platte mit zentralem Rundboss + Bohrung
Spezifikation: "Platte 80x80x10mm, Rundboss ∅40mm H15mm mittig, Bohrung ∅8mm durch Boss"

```json
{
  "description": "Platte 80x80x10mm mit Boss ∅40mm H15mm + Bohrung ∅8mm",
  "build_order": ["base", "boss", "boss_hole"],
  "features": {
    "base": {
      "type": "box",
      "params": {"x": 80.0, "y": 80.0, "z": 10.0},
      "parent": null,
      "placement": null,
      "notes": ""
    },
    "boss": {
      "type": "cylinder",
      "params": {"diameter": 40.0, "height": 15.0},
      "parent": "base",
      "placement": {
        "face": "NearestToPoint",
        "selector_point": [0.0, 0.0, 10.0],
        "position": "center",
        "offset_x": 0.0,
        "offset_y": 0.0
      },
      "notes": "Boss (Union) mittig auf Platte; NearestToPoint nach Union erforderlich"
    },
    "boss_hole": {
      "type": "hole",
      "params": {"diameter": 8.0, "depth": null},
      "parent": "boss",
      "placement": {
        "face": "NearestToPoint",
        "selector_point": [0.0, 0.0, 25.0],
        "position": "center",
        "offset_x": 0.0,
        "offset_y": 0.0
      },
      "notes": "Bohrung durch Boss (top_z = 10+15=25), depth=null → durch"
    }
  }
}
```

## Beispiel 2: Basis mit Steg (Rippe)
Spezifikation: "Basis 100x60x8mm, Längsrippe 12x50x20mm mittig"

```json
{
  "description": "Basis 100x60x8mm mit Längsrippe 12x50x20mm",
  "build_order": ["base", "rib"],
  "features": {
    "base": {
      "type": "box",
      "params": {"x": 100.0, "y": 60.0, "z": 8.0},
      "parent": null,
      "placement": null,
      "notes": ""
    },
    "rib": {
      "type": "box",
      "params": {"x": 12.0, "y": 50.0, "z": 20.0},
      "parent": "base",
      "placement": {
        "face": "NearestToPoint",
        "selector_point": [0.0, 0.0, 8.0],
        "position": "center",
        "offset_x": 0.0,
        "offset_y": 0.0
      },
      "notes": "Rippe (Union) mittig auf Basis; NearestToPoint da Union"
    }
  }
}
```

## Beispiel 3: Platte mit 4 Eckbossen + Durchgangsbohrungen
Spezifikation: "Platte 100x80x8mm, 4 Rundbossen ∅16mm H10mm in den Ecken (Randabstand 15mm), je Bohrung ∅6mm"

```json
{
  "description": "Platte 100x80x8mm mit 4 Eckbossen ∅16mm H10mm + Bohrung ∅6mm",
  "build_order": ["base", "corner_bosses", "boss_holes"],
  "features": {
    "base": {
      "type": "box",
      "params": {"x": 100.0, "y": 80.0, "z": 8.0},
      "parent": null,
      "placement": null,
      "notes": ""
    },
    "corner_bosses": {
      "type": "hole_pattern_grid",
      "params": {
        "x_count": 2,
        "y_count": 2,
        "x_spacing": 70.0,
        "y_spacing": 50.0,
        "diameter": 16.0,
        "depth": -10.0
      },
      "parent": "base",
      "placement": {
        "face": ">Z",
        "position": "center",
        "offset_x": 0.0,
        "offset_y": 0.0
      },
      "notes": "Boss-Pattern (negativ depth → Union/Extrusion); x_spacing=100-2*15=70, y_spacing=80-2*15=50"
    },
    "boss_holes": {
      "type": "hole_pattern_grid",
      "params": {
        "x_count": 2,
        "y_count": 2,
        "x_spacing": 70.0,
        "y_spacing": 50.0,
        "diameter": 6.0,
        "depth": null
      },
      "parent": "base",
      "placement": {
        "face": "NearestToPoint",
        "selector_point": [0.0, 0.0, 18.0],
        "position": "center",
        "offset_x": 0.0,
        "offset_y": 0.0
      },
      "notes": "Durchgangsbohrungen ∅6mm durch Bossen (top_z=8+10=18)"
    }
  }
}
```
