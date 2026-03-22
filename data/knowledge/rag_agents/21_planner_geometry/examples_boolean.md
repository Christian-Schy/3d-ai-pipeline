# Examples: Boolean Operations (Union / Cut between Bodies)
Tags: boolean, union, cut, intersect, combine, merge, subtract

## Beispiel 1: L-förmiger Körper (Union zweier Boxen)
Spezifikation: "L-förmiges Profil, Basis 80x20x10mm, Steg 20x60x10mm oben links"

```json
{
  "description": "L-Profil aus zwei Boxen, Basis 80x20x10mm + Steg 20x60x10mm",
  "build_order": ["base", "steg"],
  "features": {
    "base": {
      "type": "box",
      "params": {"x": 80.0, "y": 20.0, "z": 10.0},
      "parent": null,
      "placement": null,
      "notes": ""
    },
    "steg": {
      "type": "box",
      "params": {"x": 20.0, "y": 20.0, "z": 60.0},
      "parent": "base",
      "placement": {
        "face": "NearestToPoint",
        "selector_point": [-30.0, 0.0, 10.0],
        "position": "offset",
        "offset_x": -30.0,
        "offset_y": 0.0
      },
      "notes": "Union: Steg links auf Basis, NearestToPoint wegen möglicher Mehrdeutigkeit"
    }
  }
}
```

## Beispiel 2: T-Profil (Basis + zentrierter Steg)
Spezifikation: "T-Profil: Basis 100x20x8mm, Steg 12x80x8mm mittig"

```json
{
  "description": "T-Profil Basis 100x20x8mm mit Steg 12x80x8mm mittig",
  "build_order": ["base", "steg"],
  "features": {
    "base": {
      "type": "box",
      "params": {"x": 100.0, "y": 20.0, "z": 8.0},
      "parent": null,
      "placement": null,
      "notes": ""
    },
    "steg": {
      "type": "box",
      "params": {"x": 12.0, "y": 20.0, "z": 80.0},
      "parent": "base",
      "placement": {
        "face": "NearestToPoint",
        "selector_point": [0.0, 0.0, 8.0],
        "position": "center",
        "offset_x": 0.0,
        "offset_y": 0.0
      },
      "notes": "Steg mittig (offset 0,0) auf Basis, NearestToPoint nach Union"
    }
  }
}
```

## Beispiel 3: Zylinder auf Box (Boss/Dome)
Spezifikation: "Platte 60x60x8mm mit Zylinder ∅30mm, H20mm mittig oben"

```json
{
  "description": "Platte 60x60x8mm mit Zylinder ∅30mm H20mm zentral",
  "build_order": ["base_plate", "boss"],
  "features": {
    "base_plate": {
      "type": "box",
      "params": {"x": 60.0, "y": 60.0, "z": 8.0},
      "parent": null,
      "placement": null,
      "notes": ""
    },
    "boss": {
      "type": "cylinder",
      "params": {"diameter": 30.0, "height": 20.0},
      "parent": "base_plate",
      "placement": {
        "face": "NearestToPoint",
        "selector_point": [0.0, 0.0, 8.0],
        "position": "center",
        "offset_x": 0.0,
        "offset_y": 0.0
      },
      "notes": "Zylinder (Union) mittig auf Plattenoberseite"
    }
  }
}
```
