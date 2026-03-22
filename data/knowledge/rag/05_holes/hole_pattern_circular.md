# Hole Pattern Circular — Lochkreis / Polar-Lochmuster
Tags: lochkreis, polar, polarArray, kreisförmig, flansch, bolt_circle, teilkreis, gleichmäßig_kreis

## Wann verwenden
- User sagt: "Lochkreis", "Flanschbohrungen", "6 Löcher auf einem Kreis von 60mm"
- Löcher gleichmäßig auf einem Kreis verteilt

## CadQuery Code (modulare Funktion)

```python
import math

def drill_bolt_circle(body: cq.Workplane, face_selector: str,
                       hole_diameter: float, circle_diameter: float,
                       n_holes: int, depth: float = None,
                       start_angle: float = 0,
                       offset_x: float = 0, offset_y: float = 0) -> cq.Workplane:
    """Bohrt Löcher gleichmäßig auf einem Kreis (Lochkreis).

    Args:
        hole_diameter: Bohrungsdurchmesser (mm)
        circle_diameter: Durchmesser des Lochkreises (mm) — NICHT Radius
        n_holes: Anzahl der Löcher
        depth: Bohrungstiefe (None = durchgehend)
        start_angle: Startwinkel in Grad (0 = rechts/+X)
    """
    radius = circle_diameter / 2
    points = [
        (radius * math.cos(math.radians(start_angle + i * 360 / n_holes)),
         radius * math.sin(math.radians(start_angle + i * 360 / n_holes)))
        for i in range(n_holes)
    ]

    wp = (body.faces(face_selector)
          .workplane(centerOption='CenterOfBoundBox')
          .center(offset_x, offset_y)
          .pushPoints(points))

    if depth is not None:
        return wp.hole(hole_diameter, depth)
    return wp.hole(hole_diameter)


def drill_bolt_circle_polar(body: cq.Workplane, face_selector: str,
                             hole_diameter: float, circle_radius: float,
                             n_holes: int, depth: float = None) -> cq.Workplane:
    """Alternative mit polarArray (CadQuery-nativ)."""
    wp = (body.faces(face_selector)
          .workplane(centerOption='CenterOfBoundBox')
          .polarArray(circle_radius, 0, 360, n_holes))

    if depth is not None:
        return wp.hole(hole_diameter, depth)
    return wp.hole(hole_diameter)
```

## Parameter-Referenz
| Parameter | Typ | Beschreibung | Default |
|-----------|-----|--------------|---------|
| radius | float | Radius des Lochkreises (mm) — bei polarArray | — |
| startAngle | float | Startwinkel in Grad | 0 |
| angle | float | Gesamtwinkel (360 = voller Kreis) | 360 |
| count | int | Anzahl Löcher | — |

## Varianten
- pushPoints + berechnete Koordinaten: Volle Kontrolle, explizite Positionen
- `.polarArray(r, 0, 360, n)`: CadQuery-nativ, kompakter, aber Radius statt Durchmesser
- `.polarArray(r, 0, 180, 4)`: Halber Kreis mit 4 Löchern

## Häufige Fehler
1. **★ Radius vs. Durchmesser beim Lochkreis**: User sagt "Lochkreis ∅60mm" → Radius = 30mm für polarArray/pushPoints. HÄUFIGSTER FEHLER!
2. **polarArray Radius vs. pushPoints Durchmesser**: Bei pushPoints musst du selbst mit Radius rechnen
3. **math import vergessen**: Bei pushPoints-Variante → `import math` am Anfang
4. **Löcher zu nah am Rand**: Prüfen: circle_radius + hole_radius < body_radius
5. **polarArray(r, 0, 360, n)**: Bei angle=360 liegt das erste und letzte Loch NICHT übereinander — CadQuery verteilt n Löcher gleichmäßig auf 360°

## Komposition
- Lochkreis auf Flansch: `body.faces(">Z").workplane(cOBB).pushPoints([...]).hole(d)`
- Lochkreis versetzt: `.center(ox, oy)` vor `.pushPoints()` oder `.polarArray()`
- Lochkreis auf zylindrischem Boss: Erst Boss-Face selektieren, dann Lochkreis darauf
