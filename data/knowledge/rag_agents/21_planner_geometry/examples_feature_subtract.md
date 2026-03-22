# Examples: Feature Subtract (Bohrungen, Taschen, Nuten)
Tags: hole, pocket, slot, subtract, drilling, bore, cut, recess, groove

## Beispiel 1: Box mit Durchgangsbohrung mittig
Spezifikation: "Box 50x50x30mm, Durchgangsbohrung ∅10mm mittig"

```json
{
  "description": "Box 50x50x30mm mit Durchgangsbohrung ∅10mm mittig",
  "build_order": ["base", "center_hole"],
  "features": {
    "base": {
      "type": "box",
      "params": {"x": 50.0, "y": 50.0, "z": 30.0},
      "parent": null,
      "placement": null,
      "notes": ""
    },
    "center_hole": {
      "type": "hole",
      "params": {"diameter": 10.0, "depth": null},
      "parent": "base",
      "placement": {
        "face": ">Z",
        "position": "center",
        "offset_x": 0.0,
        "offset_y": 0.0
      },
      "notes": "depth=null → Durchgangsbohrung"
    }
  }
}
```

## Beispiel 2: Platte mit Sackbohrung (Blind Hole)
Spezifikation: "Platte 80x60x20mm, Sackloch ∅12mm, Tiefe 15mm, mittig"

```json
{
  "description": "Platte 80x60x20mm mit Sackloch ∅12mm T15mm mittig",
  "build_order": ["base", "blind_hole"],
  "features": {
    "base": {
      "type": "box",
      "params": {"x": 80.0, "y": 60.0, "z": 20.0},
      "parent": null,
      "placement": null,
      "notes": ""
    },
    "blind_hole": {
      "type": "hole",
      "params": {"diameter": 12.0, "depth": 15.0},
      "parent": "base",
      "placement": {
        "face": ">Z",
        "position": "center",
        "offset_x": 0.0,
        "offset_y": 0.0
      },
      "notes": "Sackloch: depth=15.0 (< Wandstärke 20mm)"
    }
  }
}
```

## Beispiel 3: Box mit Rechtecktasche (Pocket)
Spezifikation: "Block 70x50x25mm, rechteckige Tasche 40x30mm, Tiefe 10mm, mittig"

```json
{
  "description": "Block 70x50x25mm mit Tasche 40x30x10mm mittig",
  "build_order": ["base", "pocket"],
  "features": {
    "base": {
      "type": "box",
      "params": {"x": 70.0, "y": 50.0, "z": 25.0},
      "parent": null,
      "placement": null,
      "notes": ""
    },
    "pocket": {
      "type": "pocket",
      "params": {"x": 40.0, "y": 30.0, "depth": 10.0},
      "parent": "base",
      "placement": {
        "face": ">Z",
        "position": "center",
        "offset_x": 0.0,
        "offset_y": 0.0
      },
      "notes": "Rechtecktasche mittig, Tiefe 10mm < Wandstärke 25mm"
    }
  }
}
```

## Beispiel 4: Box mit Nut (Slot)
Spezifikation: "Block 80x40x20mm, durchgehende Nut 8mm breit, 6mm tief, mittig in Y"

```json
{
  "description": "Block 80x40x20mm mit Nut 8x6mm durchgehend in X",
  "build_order": ["base", "slot"],
  "features": {
    "base": {
      "type": "box",
      "params": {"x": 80.0, "y": 40.0, "z": 20.0},
      "parent": null,
      "placement": null,
      "notes": ""
    },
    "slot": {
      "type": "slot",
      "params": {"width": 8.0, "depth": 6.0, "length": null},
      "parent": "base",
      "placement": {
        "face": ">Z",
        "position": "center",
        "offset_x": 0.0,
        "offset_y": 0.0
      },
      "notes": "Nut in X-Richtung, length=null → durchgehend"
    }
  }
}
```
