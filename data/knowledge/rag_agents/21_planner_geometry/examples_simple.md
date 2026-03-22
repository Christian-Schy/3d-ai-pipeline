# Examples: Simple Models (Grundkörper + Modifikator)
Tags: simple, box, cylinder, sphere, chamfer, fillet, shell, grundkörper

## Beispiel 1: Würfel mit Fase an allen Kanten
Spezifikation: "30mm Würfel mit 2mm Fase an allen Kanten"

```json
{
  "description": "Würfel 30x30x30mm mit Fase 2mm an allen Kanten",
  "build_order": ["base_cube", "chamfer_all_edges"],
  "features": {
    "base_cube": {
      "type": "box",
      "params": {"x": 30.0, "y": 30.0, "z": 30.0},
      "parent": null,
      "placement": null,
      "notes": ""
    },
    "chamfer_all_edges": {
      "type": "chamfer",
      "params": {"size": 2.0},
      "parent": "base_cube",
      "placement": null,
      "notes": "edges().chamfer(2.0) — alle 12 Kanten"
    }
  }
}
```

## Beispiel 2: Zylinder mit Verrundung oben
Spezifikation: "Zylinder ∅40mm, Höhe 60mm, obere Kante mit 3mm Radius verrunden"

```json
{
  "description": "Zylinder ∅40mm H60mm mit Fillet R3mm oben",
  "build_order": ["base_cylinder", "fillet_top"],
  "features": {
    "base_cylinder": {
      "type": "cylinder",
      "params": {"diameter": 40.0, "height": 60.0},
      "parent": null,
      "placement": null,
      "notes": ""
    },
    "fillet_top": {
      "type": "fillet",
      "params": {"radius": 3.0},
      "parent": "base_cylinder",
      "placement": null,
      "notes": "edges('>Z').fillet(3.0) — nur obere Kante"
    }
  }
}
```

## Beispiel 3: Hohle Box (Shell)
Spezifikation: "Box 50x40x30mm, 2mm Wandstärke, oben offen"

```json
{
  "description": "Hohle Box 50x40x30mm, Wandstärke 2mm",
  "build_order": ["base_box", "shell"],
  "features": {
    "base_box": {
      "type": "box",
      "params": {"x": 50.0, "y": 40.0, "z": 30.0},
      "parent": null,
      "placement": null,
      "notes": ""
    },
    "shell": {
      "type": "shell",
      "params": {"thickness": 2.0},
      "parent": "base_box",
      "placement": null,
      "notes": "shell(2.0) — öffnet >Z Face"
    }
  }
}
```
