# Multi-Part Beispiele — Platten, Aufsätze, Kombinationen
Tags: multi, part, platte, aufsatz, bündig, flush, stacking, zusammenbau

## Beispiel 1: Basis + Aufsatz rechts + Bohrung

Spec: "Platte 100x100x20. Rechts bündig ein Aufsatz 20x80x40 stehend. Bohrung ∅10 durch den Aufsatz."

```json
{
  "description": "Platte mit Aufsatz rechts und Durchgangsbohrung",
  "build_order": ["base", "plate_right", "hole_through"],
  "features": {
    "base": {
      "type": "box", "params": {"x": 100, "y": 100, "z": 20},
      "parent": null, "placement": null, "operation": "add"
    },
    "plate_right": {
      "type": "extrusion_rect", "params": {"x": 20, "y": 80, "z": 40},
      "parent": "base",
      "placement": {"face": ">Z", "alignment": "flush_right", "offset_x": 40.0, "offset_y": 0.0, "notes": ""},
      "operation": "add"
    },
    "hole_through": {
      "type": "hole_single", "params": {"diameter": 10, "depth": null},
      "parent": "plate_right",
      "placement": {"face": ">Z", "alignment": "centered", "offset_x": 0, "offset_y": 0, "notes": ""},
      "operation": "subtract"
    }
  }
}
```

## Beispiel 2: Würfel mit Bohrungen auf mehreren Seiten + Nut

Spec: "50mm Würfel. Rechts eine Bohrung oben rechts 20mm von den Kanten, ∅10, 10mm tief. Eine Bohrung von unten 10mm entfernt und von der linken Kante 15mm entfernt, ∅20, 20mm tief. Auf der linken Seite zentral eine Bohrung ∅25, 10mm tief. Hinten eine Nut entlang Y."

★ ANALYSE der Faces und Offsets:
- "Rechts eine Bohrung" → face=">X" (Richtungswort VOR Feature = Face!)
- "oben rechts 20mm von Kanten" → Offset auf >X Face (Y×Z=50×50): offset_x=+5, offset_y=+5
- "von unten 10mm, von der linken Kante 15mm" → KEINE Face-Angabe! "Kante"=Offset, NICHT Face!
  → Default face=">Z". offset_x=-(50/2-15)=-10, offset_y=-(50/2-10)=-15
- "auf der linken Seite zentral" → face="<X", centered
- "hinten eine Nut" → face=">Y"

```json
{
  "description": "50mm Würfel mit Bohrungen auf 3 Seiten und Nut",
  "build_order": ["base", "hole_right_top", "hole_top_offset", "hole_left_center", "slot_back"],
  "features": {
    "base": {
      "type": "box", "params": {"x": 50, "y": 50, "z": 50},
      "parent": null, "placement": null, "operation": "add"
    },
    "hole_right_top": {
      "type": "hole_single", "params": {"diameter": 10, "depth": 10},
      "parent": "base",
      "placement": {"face": ">X", "alignment": "centered", "offset_x": 5.0, "offset_y": 5.0, "notes": "oben rechts auf rechter Seite, 20mm von Kanten: 50/2-20=5"},
      "operation": "subtract"
    },
    "hole_top_offset": {
      "type": "hole_single", "params": {"diameter": 20, "depth": 20},
      "parent": "base",
      "placement": {"face": ">Z", "alignment": "centered", "offset_x": -10.0, "offset_y": -15.0, "notes": "Kante=Offset! links 15mm: -(25-15)=-10, unten 10mm: -(25-10)=-15"},
      "operation": "subtract"
    },
    "hole_left_center": {
      "type": "hole_single", "params": {"diameter": 25, "depth": 10},
      "parent": "base",
      "placement": {"face": "<X", "alignment": "centered", "offset_x": 0, "offset_y": 0, "notes": "linke Seite zentral"},
      "operation": "subtract"
    },
    "slot_back": {
      "type": "slot", "params": {"width": 5, "depth": 5, "length": null},
      "parent": "base",
      "placement": {"face": ">Y", "alignment": "centered", "offset_x": 0, "offset_y": 0, "notes": "Nut entlang Y"},
      "operation": "subtract"
    }
  }
}
```

## Beispiel 3: Platte mit Platte links bündig hochkant

Spec: "Platte 100x60x20. Links bündig eine Platte 60x60x20 hochkant."

"hochkant" → größte Dim wird Z → 60x60x20 wird x=60, y=20, z=60
"links bündig" → face=">Z", alignment="flush_left"
offset_x = -(100/2 - 60/2) = -20.0

```json
{
  "description": "Platte mit Seitenplatte links",
  "build_order": ["base", "plate_left"],
  "features": {
    "base": {
      "type": "box", "params": {"x": 100, "y": 60, "z": 20},
      "parent": null, "placement": null, "operation": "add"
    },
    "plate_left": {
      "type": "extrusion_rect", "params": {"x": 60, "y": 20, "z": 60},
      "parent": "base",
      "placement": {"face": ">Z", "alignment": "flush_left", "offset_x": -20.0, "offset_y": 0.0, "notes": "hochkant: 60x60x20 → y/z getauscht"},
      "operation": "add"
    }
  }
}
```

## Beispiel 4: Bohrungsreihe auf Seitenfläche

Spec: "Platte 20x40x200. Rechte Fläche: ab 40mm vom Rand 4 Bohrungen, 20mm Abstand, ∅10, 10mm tief."

```json
{
  "description": "Platte mit linearem Bohrungsmuster",
  "build_order": ["base", "holes_linear"],
  "features": {
    "base": {
      "type": "box", "params": {"x": 20, "y": 40, "z": 200},
      "parent": null, "placement": null, "operation": "add"
    },
    "holes_linear": {
      "type": "hole_pattern_linear",
      "params": {"count": 4, "spacing": 20, "start_offset": 40, "hole_diameter": 10, "depth": 10, "direction": "y"},
      "parent": "base",
      "placement": {"face": ">X", "alignment": "centered", "offset_x": 0, "offset_y": 0, "notes": ""},
      "operation": "subtract"
    }
  }
}
```
