# Examples: Modify (Blueprint anpassen, Parameter ändern, Feature hinzufügen)
Tags: modify, update, change, add_feature, remove, adjust, parameter, edit, revision

## Beispiel 1: Maßänderung — Box größer machen
Ursprungs-Blueprint: Box 30x30x30mm
Anfrage: "mach die Box 50x50x40mm"

```json
{
  "description": "Box 50x50x40mm (geändert von 30x30x30)",
  "build_order": ["base_cube"],
  "features": {
    "base_cube": {
      "type": "box",
      "params": {"x": 50.0, "y": 50.0, "z": 40.0},
      "parent": null,
      "placement": null,
      "notes": "Parameter geändert: 30→50, 30→50, 30→40"
    }
  }
}
```

## Beispiel 2: Feature hinzufügen — Bohrung zu bestehendem Modell
Ursprungs-Blueprint: Box 60x40x20mm ohne Bohrung
Anfrage: "füge eine Bohrung ∅10mm mittig hinzu"

```json
{
  "description": "Box 60x40x20mm mit Durchgangsbohrung ∅10mm (Bohrung neu hinzugefügt)",
  "build_order": ["base", "center_hole"],
  "features": {
    "base": {
      "type": "box",
      "params": {"x": 60.0, "y": 40.0, "z": 20.0},
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
      "notes": "Neu hinzugefügt: Durchgangsbohrung mittig"
    }
  }
}
```

## Beispiel 3: Fase hinzufügen zu fertigem Modell
Ursprungs-Blueprint: Zylinder ∅50mm H80mm ohne Modifikator
Anfrage: "alle Kanten mit 2mm Fase versehen"

```json
{
  "description": "Zylinder ∅50mm H80mm mit Chamfer 2mm (Fase neu hinzugefügt)",
  "build_order": ["base_cylinder", "chamfer_all"],
  "features": {
    "base_cylinder": {
      "type": "cylinder",
      "params": {"diameter": 50.0, "height": 80.0},
      "parent": null,
      "placement": null,
      "notes": ""
    },
    "chamfer_all": {
      "type": "chamfer",
      "params": {"size": 2.0},
      "parent": "base_cylinder",
      "placement": null,
      "notes": "Neu hinzugefügt: edges().chamfer(2.0) — alle Kanten"
    }
  }
}
```

## Beispiel 4: Feature entfernen
Ursprungs-Blueprint: Box mit Fase + Bohrung
Anfrage: "entferne die Fase"

```json
{
  "description": "Box 40x40x20mm mit Bohrung (Chamfer entfernt)",
  "build_order": ["base", "center_hole"],
  "features": {
    "base": {
      "type": "box",
      "params": {"x": 40.0, "y": 40.0, "z": 20.0},
      "parent": null,
      "placement": null,
      "notes": ""
    },
    "center_hole": {
      "type": "hole",
      "params": {"diameter": 8.0, "depth": null},
      "parent": "base",
      "placement": {
        "face": ">Z",
        "position": "center",
        "offset_x": 0.0,
        "offset_y": 0.0
      },
      "notes": ""
    }
  }
}
```

## Beispiel 5: Lochmuster-Parameter anpassen
Ursprungs-Blueprint: 2x2 Löcher ∅6mm, spacing 40mm
Anfrage: "mach die Löcher ∅10mm und den Abstand 50mm"

```json
{
  "description": "Platte 80x80x10mm mit 2x2 Löchern ∅10mm spacing 50mm (geändert)",
  "build_order": ["base", "corner_holes"],
  "features": {
    "base": {
      "type": "box",
      "params": {"x": 80.0, "y": 80.0, "z": 10.0},
      "parent": null,
      "placement": null,
      "notes": ""
    },
    "corner_holes": {
      "type": "hole_pattern_grid",
      "params": {
        "x_count": 2,
        "y_count": 2,
        "x_spacing": 50.0,
        "y_spacing": 50.0,
        "diameter": 10.0,
        "depth": null
      },
      "parent": "base",
      "placement": {
        "face": ">Z",
        "position": "center",
        "offset_x": 0.0,
        "offset_y": 0.0
      },
      "notes": "diameter 6→10mm, spacing 40→50mm"
    }
  }
}
```
