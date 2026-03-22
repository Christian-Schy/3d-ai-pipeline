# Feature Tree Patterns — ★ Wie ein Feature Tree aufgebaut wird
Tags: feature_tree, blueprint, aufbau, struktur, build_order

## Feature Tree JSON-Struktur

```json
{
  "description": "Kurzbeschreibung des Gesamtteils",
  "build_order": ["base", "feature_a", "feature_b", "hole_1"],
  "features": {
    "feature_id": {
      "type": "Feature-Typ aus Enum",
      "params": { ... },
      "parent": "parent_feature_id oder null",
      "placement": { "face": "...", "position": "..." },
      "notes": "Zusatzinfo für den Coder"
    }
  }
}
```

## Build-Order-Regeln
1. Base IMMER zuerst
2. Parent IMMER vor Child
3. Subtraktive Features auf Basis VOR additiven Features (Union)
4. Subtraktive Features auf additiven Features NACH deren Union
5. Fillet/Chamfer IMMER am Ende

## Korrekte Reihenfolge
```
base → [Löcher in Basis] → [Additive Features] → [Löcher in Additiven] → [Fillet/Chamfer]
```

## Beispiel: Platte + Steg + Eckbohrungen + Steg-Bohrung

```json
{
  "description": "100x80x15 Platte, Steg rechts, 4 Eckbohrungen, Bohrung im Steg",
  "build_order": ["base", "corner_holes", "steg_rechts", "steg_bohrung"],
  "features": {
    "base": {
      "type": "base_plate",
      "params": {"x": 100, "y": 80, "z": 15},
      "parent": null,
      "placement": null
    },
    "corner_holes": {
      "type": "hole_single",
      "params": {"diameter": 5, "depth": null, "count": 4, "inset": 10},
      "parent": "base",
      "placement": {"face": ">Z", "position": "corners"}
    },
    "steg_rechts": {
      "type": "extrusion_rect",
      "params": {"x": 10, "y": 80, "z": 20},
      "parent": "base",
      "placement": {"face": ">Z", "position": "flush_right"},
      "notes": "Bündig am rechten Rand der Basis"
    },
    "steg_bohrung": {
      "type": "hole_single",
      "params": {"diameter": 8, "depth": null},
      "parent": "steg_rechts",
      "placement": {"face": ">X", "position": "center"},
      "notes": "Querbohrung von rechts, zentriert im Steg"
    }
  }
}
```

## Warum corner_holes VOR steg_rechts?
- corner_holes sitzt auf base (>Z)
- Nach Union mit steg_rechts ist >Z der Basis nicht mehr eindeutig selektierbar
- Deshalb: Basis-Bohrungen BEVOR Steg aufgesetzt wird

## Typische Patterns

### Flanschplatte
base → boss_center → bolt_circle_on_boss → center_hole → fillets

### Gehäuse
base → pocket_inside → mounting_holes → stiffener_ribs → fillets

### Rotor
base_cylinder → blades(polar_pattern) → center_hole → balance_holes → fillets
