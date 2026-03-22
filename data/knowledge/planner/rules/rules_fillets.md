# Fillet- und Chamfer-Regeln

## Typen
- chamfer: Fase (45°), params={size: float}
- fillet: Verrundung, params={radius: float}

## Wichtigste Regel: IMMER ZULETZT in build_order
Fillet/Chamfer MÜSSEN das letzte (oder die letzten) Features in build_order sein.
Boolean-Ops (Union/Cut) NACH einem Fillet würden die Verrundungen zerstören.

## Placement für Fillet/Chamfer
- Alle Kanten: placement=null, notes="edges().chamfer(size)"
- Nur obere Kanten: notes="edges('>Z').chamfer(size)"
- Nur vertikale Kanten: notes="edges('|Z').fillet(radius)"
- operation: "modify" (kein Union, kein Cut)

## Blueprint-Beispiel: Würfel mit Fase
{
  "build_order": ["base", "chamfer_all"],
  "features": {
    "base": {"type": "box", "params": {"x": 30, "y": 30, "z": 30}, "parent": null},
    "chamfer_all": {
      "type": "chamfer",
      "params": {"size": 2.0},
      "parent": "base",
      "placement": null,
      "notes": "edges().chamfer(2.0) — alle 12 Kanten"
    }
  }
}

## Häufige Fehler
- Fillet/Chamfer nicht am Ende → Boolean danach zerstört sie
- size/radius > kleinste Kante → Topologiefehler
- Fillet mit radius > Wandstärke/2 → unmöglich
- chamfer und fillet auf gleichen Kanten → Konflikte
