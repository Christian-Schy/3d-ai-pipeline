# Zwei-Schritt-Positionierung — Erst Feature, dann Zusammenbau
Tags: position, placement, zusammenbau, assembly, feature, teil, isoliert

## Grundregel: Zwei getrennte Aufgaben

**Schritt 1: Features AM Einzelteil** (Bohrung, Nut, Fase)
→ Betrachte das Teil ALLEIN. Wo sitzt das Feature auf DIESEM Teil?

**Schritt 2: Zusammenbau** (Teil auf anderem Teil)
→ Wie sitzt das Teil auf seinem Parent? Face, Alignment, Orientierung.

Diese Schritte sind UNABHÄNGIG voneinander!

## Schritt 1: Feature am Einzelteil

Denke dir das Teil isoliert vor — ohne andere Teile.
Eine Platte 20×80×40 mit Bohrung auf der 80×40 Seite:

```json
"hole": {
  "face": ">X",
  "alignment": "centered",
  "face_hint": "von der 80×40 Seite"
}
```

Das hat NICHTS mit der Basis oder dem Zusammenbau zu tun.

## Schritt 2: Zusammenbau

"Platte oben rechts auf der Basis, 20×80 Fläche liegt auf, bündig rechts"

```json
"plate_right": {
  "face": ">Z",
  "alignment": "flush_right",
  "orientation_hint": "20×80 Fläche liegt auf"
}
```

## Vollständiges Beispiel

Spec: "Basis 100×100×20. Platte 20×80×40 rechts auf Basis, 20×80 liegt auf. Bohrung ∅10 auf der 80×40 Seite zentral durch."

Schritt 1 — Feature (Bohrung auf Platte, isoliert betrachten):
  Platte ist 20×80×40. "80×40 Seite" = >X (weil Y×Z = 80×40)
  → hole: face=">X", centered

Schritt 2 — Zusammenbau (Platte auf Basis):
  "rechts auf Basis" → face=">Z", alignment="flush_right"
  "20×80 liegt auf" → orientation_hint durchreichen

Ergebnis:
```json
{
  "positions": {
    "plate_right": {
      "face": ">Z",
      "alignment": "flush_right",
      "offset_x": null,
      "offset_y": null,
      "orientation_hint": "20×80 Fläche liegt auf",
      "face_hint": null,
      "axis_hint": null
    },
    "hole": {
      "face": ">X",
      "alignment": "centered",
      "offset_x": null,
      "offset_y": null,
      "orientation_hint": null,
      "face_hint": "von der 80×40 Seite",
      "axis_hint": null
    }
  }
}
```

## Beispiel: Würfel mit Nut und Bohrung

Spec: "Würfel 30mm. Nut 5×5 oben entlang Y. Bohrung ∅10 oben, 10mm von Unterkante."

Nur Schritt 1 (alles am selben Teil):
- Nut: face=">Z" (oben), alignment="centered", axis_hint="Y"
- Bohrung: face=">Z" (oben), "10mm von Unterkante (-Y)"
  → Parent Y=30, offset_y = -(30/2 - 10) = -5.0

```json
{
  "positions": {
    "groove": {
      "face": ">Z",
      "alignment": "centered",
      "offset_x": null,
      "offset_y": null,
      "orientation_hint": null,
      "face_hint": null,
      "axis_hint": "Y"
    },
    "hole": {
      "face": ">Z",
      "alignment": "centered",
      "offset_x": 0.0,
      "offset_y": -5.0,
      "orientation_hint": null,
      "face_hint": null,
      "axis_hint": null
    }
  }
}
```
