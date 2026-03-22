# Bolt Circle — Lochkreis für Flanschverbindungen
Tags: lochkreis, flansch, bolt_circle, schraubenkreis, befestigung, montage, flanschbohrung

## Wann verwenden
- User sagt: "Lochkreis", "Flansch", "Befestigungslöcher im Kreis"
- Standardmäßige Flanschverbindung mit gleichmäßig verteilten Schrauben

## CadQuery Code (modulare Funktion)

```python
import math

def add_bolt_circle(body: cq.Workplane, face_selector: str,
                     circle_diameter: float, hole_diameter: float,
                     n_holes: int, start_angle: float = 0,
                     depth: float = None,
                     center_x: float = 0, center_y: float = 0) -> cq.Workplane:
    """Erzeugt einen Lochkreis (Bolt Circle Pattern).

    Args:
        circle_diameter: Teilkreisdurchmesser (mm)
        hole_diameter: Bohrungsdurchmesser (mm)
        n_holes: Anzahl Bohrungen
        start_angle: Startwinkel in Grad (0° = +X Richtung)
        depth: Bohrungstiefe (None = durch)
        center_x, center_y: Zentrum des Lochkreises relativ zur Face-Mitte
    """
    r = circle_diameter / 2
    points = [
        (center_x + r * math.cos(math.radians(start_angle + i * 360 / n_holes)),
         center_y + r * math.sin(math.radians(start_angle + i * 360 / n_holes)))
        for i in range(n_holes)
    ]

    wp = (body.faces(face_selector)
          .workplane(centerOption='CenterOfBoundBox')
          .pushPoints(points))

    if depth is not None:
        return wp.hole(hole_diameter, depth)
    return wp.hole(hole_diameter)
```

## Typische Werte
| Schraubengröße | Bohrung ∅ | Kopf-Ø (Cbore) | Typischer Teilkreis |
|---------------|-----------|-----------------|---------------------|
| M3 | 3.4 | 6.5 | 20-40mm |
| M4 | 4.5 | 8.0 | 30-50mm |
| M5 | 5.5 | 9.5 | 40-60mm |
| M6 | 6.6 | 11.0 | 50-80mm |
| M8 | 9.0 | 14.0 | 60-100mm |

## Häufige Fehler
1. **★★★ Radius vs. Durchmesser**: "Lochkreis ∅60" → Radius = 30 für die Berechnung!
2. **Löcher am Rand**: Prüfe: circle_diameter/2 + hole_diameter/2 < body_breite/2
3. **Start-Winkel**: 0° = rechts (+X). Für erstes Loch oben: start_angle=90
4. **math import**: Immer `import math` am Anfang

## Komposition
- Lochkreis auf Platte: Direkt auf `>Z` Face
- Lochkreis auf zylindrischer Erhöhung (Boss): Face des Boss selektieren → Lochkreis darauf
- Lochkreis mit Senkbohrungen: `.cboreHole()` statt `.hole()` im Pattern
