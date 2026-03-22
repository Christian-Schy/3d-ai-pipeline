# Face Selector Planning — Welchen Selektor für welche Situation
Tags: face, selektor, planung, auswahl, selector

## Entscheidungsbaum

```
Feature auf Basis (vor Union)?
├── JA → face: ">Z", ">X" etc. (einfache Selektoren reichen)
│
└── NEIN → Feature nach Union?
    ├── Feature auf HÖCHSTEM Körper?
    │   └── JA → face: ">Z" kann funktionieren, aber unsicher
    │
    └── Feature auf NICHT-HÖCHSTEM Körper?
        └── → face: "NearestToPoint" (IMMER!)
            → Punkt berechnen: (parent_center_x, parent_center_y, parent_top_z)
```

## Selektor-Zuweisung im Feature Tree

### Vor jeder Union
- Basis-Features: einfache Selektoren (">Z", ">X")
- Sicher, weil nur ein Körper existiert

### Nach Union
- IMMER NearestToPointSelector mit berechnetem Punkt
- Punkt = Zentrum der Ziel-Face

### Punkt-Berechnung für NearestToPointSelector
Top-Face eines Features:
  x = feature_translate_x
  y = feature_translate_y
  z = Summe aller darunterliegenden Höhen

Seiten-Face eines Features:
  x = feature_translate_x ± feature_breite/2
  y = feature_translate_y
  z = feature_z_mitte

## Im Feature Tree angeben

```json
"placement": {
  "face": ">Z",
  "selector_hint": "simple"
}
```
oder
```json
"placement": {
  "face": "NearestToPoint",
  "selector_point": [25, -25, 35],
  "selector_hint": "after_union"
}
```

## Regel
Wenn parent != "base" ODER es schon eine Union gab:
→ IMMER selector_hint: "after_union" + selector_point berechnen
