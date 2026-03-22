# Pattern on Raised Surface — Muster auf erhöhter Fläche
Tags: muster_auf_aufsatz, pattern_raised, lochkreis_auf_boss, array_auf_feature

## Wann verwenden
- Lochraster oder Lochkreis auf einem Boss/Steg (nicht auf der Basis)
- Muster das auf einem Feature sitzt, nicht auf dem Grundkörper

## CadQuery Code (modulare Funktion)

```python
import math
from cadquery.selectors import NearestToPointSelector

def drill_pattern_on_raised(body: cq.Workplane,
                             feature_center_x: float,
                             feature_center_y: float,
                             feature_top_z: float,
                             pattern_type: str,
                             hole_diameter: float,
                             **params) -> cq.Workplane:
    """Bohrt ein Muster auf einer erhöhten Fläche.

    Args:
        feature_center_x/y: XY-Zentrum des Features
        feature_top_z: Z-Höhe der Feature-Oberseite
        pattern_type: "grid" oder "circular"
    """
    wp = (body.faces(NearestToPointSelector(
              (feature_center_x, feature_center_y, feature_top_z)))
          .workplane(centerOption='CenterOfBoundBox'))

    if pattern_type == "grid":
        xs = params.get('x_spacing', 20)
        ys = params.get('y_spacing', 20)
        xn = params.get('x_count', 2)
        yn = params.get('y_count', 2)
        return wp.rArray(xs, ys, xn, yn).hole(hole_diameter)

    elif pattern_type == "circular":
        circle_d = params.get('circle_diameter', 40)
        n = params.get('n_holes', 6)
        r = circle_d / 2
        points = [
            (r * math.cos(2 * math.pi * i / n),
             r * math.sin(2 * math.pi * i / n))
            for i in range(n)
        ]
        return wp.pushPoints(points).hole(hole_diameter)


# ★ VOLLSTÄNDIGES BEISPIEL: Flanschplatte mit Boss + Lochkreis auf Boss
def example_flange_with_bolt_circle():
    # 1. Basis
    base = cq.Workplane("XY").box(120, 120, 10, centered=(True, True, False))

    # 2. Zylindrischer Boss mittig
    body = (base.faces(">Z")
            .workplane(centerOption='CenterOfBoundBox')
            .circle(40).extrude(8))
    # Boss-Top bei Z=18, Zentrum bei (0, 0)

    # 3. Lochkreis auf dem Boss
    result = drill_pattern_on_raised(
        body,
        feature_center_x=0, feature_center_y=0,
        feature_top_z=18,
        pattern_type="circular",
        hole_diameter=6.6,  # M6 Durchgang
        circle_diameter=60,
        n_holes=6
    )

    # 4. Zentrale Bohrung durch alles
    result = (result.faces(NearestToPointSelector((0, 0, 18)))
              .workplane(centerOption='CenterOfBoundBox')
              .hole(20))

    return result
```

## Häufige Fehler
1. **Pattern-Radius > Feature-Radius**: Löcher ragen über das Feature hinaus → prüfen: circle_r + hole_r < feature_r
2. **NearestToPointSelector Z falsch**: feature_top_z = basis_höhe + feature_höhe
3. **rArray auf kleinem Feature**: Grid kann über die Feature-Grenzen hinausragen
