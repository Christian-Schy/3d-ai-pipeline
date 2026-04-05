# Per-Part-Denken — Jedes Teil isoliert betrachten
Tags: teil, isoliert, unabhängig, parent, zuordnung, per-part

## Grundregel: Denke PRO TEIL

Betrachte jedes Teil EINZELN. Features eines Teils haben NICHTS mit anderen Teilen zu tun.

Ablauf:
1. Welche Teile gibt es? (Jedes Teil mit eigenen Maßen)
2. Für JEDES Teil: Welche Features hat ES? (Bohrung, Nut, etc.)
3. Zusammenbau ist ein SEPARATER Schritt — nicht deine Aufgabe!

## Beispiel 1: Basis + Platte mit Bohrung

Spec: "Basis 100×100×20. Platte 20×80×40. Bohrung ∅10 auf der 80×40 Seite zentral durch."

DENKE SO:
- Teil 1: Basis 100×100×20 → keine Features → fertig
- Teil 2: Platte 20×80×40 → hat eine Bohrung
  - Bohrung gehört zur PLATTE (nicht zur Basis!)
  - parent=plate, op=subtract, diameter=10, depth=null

Ergebnis:
```json
{
  "assignments": {
    "base": {"parent": null, "operation": "add", "params": {"x": 100, "y": 100, "z": 20}},
    "plate_right": {"parent": "base", "operation": "add", "params": {"x": 20, "y": 80, "z": 40}},
    "hole": {"parent": "plate_right", "operation": "subtract", "params": {"diameter": 10, "depth": null}}
  },
  "build_order": ["base", "plate_right", "hole"]
}
```

## Beispiel 2: Würfel mit Nut und Bohrung

Spec: "Würfel 30mm. Nut 5×5 oben entlang Y. Bohrung ∅10 29mm tief, 10mm von Unterkante."

DENKE SO:
- Teil 1: Würfel 30×30×30 → hat Nut + Bohrung
  - Nut: parent=base, op=subtract, width=5, depth=5, length=30
  - Bohrung: parent=base, op=subtract, diameter=10, depth=29

Ergebnis:
```json
{
  "assignments": {
    "base": {"parent": null, "operation": "add", "params": {"x": 30, "y": 30, "z": 30}},
    "groove": {"parent": "base", "operation": "subtract", "params": {"width": 5, "depth": 5, "length": 30}},
    "hole": {"parent": "base", "operation": "subtract", "params": {"diameter": 10, "depth": 29}}
  },
  "build_order": ["base", "groove", "hole"]
}
```

## Beispiel 3: Basis + Aufsatz + Bohrung im Aufsatz

Spec: "Basis 100×100×20. Aufsatz 50×50×20 oben mittig. Bohrung ∅8 durch den Aufsatz."

DENKE SO:
- Teil 1: Basis → keine Features
- Teil 2: Aufsatz → hat Bohrung
  - Bohrung: parent=pad (NICHT base!), weil "durch den Aufsatz"

```json
{
  "assignments": {
    "base": {"parent": null, "operation": "add", "params": {"x": 100, "y": 100, "z": 20}},
    "pad": {"parent": "base", "operation": "add", "params": {"x": 50, "y": 50, "z": 20}},
    "hole": {"parent": "pad", "operation": "subtract", "params": {"diameter": 8, "depth": null}}
  },
  "build_order": ["base", "pad", "hole"]
}
```
