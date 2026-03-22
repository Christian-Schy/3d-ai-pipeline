# Hole in Extrusion — ★ Bohrung in extrudiertem Feature
Tags: bohrung_in_aufsatz, hole_in_extrusion, steg_bohrung, darin, loch_im_feature

## Wann verwenden
- User sagt: "Bohrung darin", "Loch im Steg", "durch den Aufsatz bohren"
- Bohrung soll IN einem Feature sitzen, nicht in der Basis
- ★ Häufiges Muster bei mechanischen Teilen

## CadQuery Code (modulare Funktion)

```python
from cadquery.selectors import NearestToPointSelector

def drill_hole_in_extrusion_top(body: cq.Workplane,
                                 extrusion_center_x: float,
                                 extrusion_center_y: float,
                                 extrusion_top_z: float,
                                 hole_diameter: float,
                                 hole_depth: float = None,
                                 offset_x: float = 0,
                                 offset_y: float = 0) -> cq.Workplane:
    """Bohrt von oben in ein extrudiertes Feature.

    Args:
        extrusion_center_x/y: XY-Position des Extrusions-Zentrums
        extrusion_top_z: Z-Höhe der Extrusions-Oberseite
        offset_x/y: Versatz vom Extrusions-Zentrum
    """
    wp = (body.faces(NearestToPointSelector(
              (extrusion_center_x, extrusion_center_y, extrusion_top_z)))
          .workplane(centerOption='CenterOfBoundBox')
          .center(offset_x, offset_y))

    if hole_depth is not None:
        return wp.hole(hole_diameter, hole_depth)
    return wp.hole(hole_diameter)


def drill_hole_in_extrusion_side(body: cq.Workplane,
                                  extrusion_face_x: float,
                                  extrusion_center_y: float,
                                  extrusion_center_z: float,
                                  hole_diameter: float,
                                  hole_depth: float = None) -> cq.Workplane:
    """Bohrt von der Seite in ein extrudiertes Feature.

    Args:
        extrusion_face_x: X-Position der Seitenfläche des Features
        extrusion_center_y/z: YZ-Zentrum der Seitenfläche
    """
    wp = (body.faces(NearestToPointSelector(
              (extrusion_face_x, extrusion_center_y, extrusion_center_z)))
          .workplane(centerOption='CenterOfBoundBox'))

    if hole_depth is not None:
        return wp.hole(hole_diameter, hole_depth)
    return wp.hole(hole_diameter)


# ★ VOLLSTÄNDIGES BEISPIEL
def example_plate_steg_hole():
    """Platte 100x100x20 + Steg 10x100x20 rechts + Bohrung ∅10 in Steg von rechts."""

    # 1. Basis
    base = cq.Workplane("XY").box(100, 100, 20, centered=(True, True, False))
    # Basis: X von -50 bis +50, Y von -50 bis +50, Z von 0 bis 20

    # 2. Steg rechts: 10x100x20, bündig am rechten Rand
    # Steg-Zentrum X = 50 - 10/2 = 45 (bündig rechts)
    steg = cq.Workplane("XY").box(10, 100, 20).translate((45, 0, 30))
    body = base.union(steg).clean()
    # Steg: X von 40 bis 50, Z von 20 bis 40

    # 3. Bohrung von RECHTS in den Steg, zentriert
    # Rechte Seitenfläche des Stegs: X=50, Zentrum Y=0, Z=30
    result = drill_hole_in_extrusion_side(
        body,
        extrusion_face_x=50,
        extrusion_center_y=0,
        extrusion_center_z=30,
        hole_diameter=10
    )
    return result
```

## Koordinaten-Berechnung

Für Bohrung VON OBEN ins Feature:
```
extrusion_top_z = basis_höhe + feature_höhe
extrusion_center_x = feature_translate_x
extrusion_center_y = feature_translate_y
```

Für Bohrung VON DER SEITE ins Feature:
```
# Rechte Seite des Features:
extrusion_face_x = feature_translate_x + feature_breite / 2
extrusion_center_y = feature_translate_y
extrusion_center_z = basis_höhe + feature_höhe / 2
```

## Häufige Fehler
1. **★ "darin" → NearestToPointSelector**: "Bohrung darin" = im Feature, nicht in der Basis. IMMER NearestToPointSelector mit Feature-Koordinaten
2. **Seitenbohrung Z-Koordinate**: Z-Zentrum der Seitenfläche = basis_höhe + feature_höhe/2, NICHT feature_höhe/2
3. **Bohrung geht durch Basis**: Wenn hole_depth > feature_höhe → Bohrung reicht in die Basis. depth explizit setzen
4. **Face-Verwechslung**: Bei Seitenbohrung kann NearestToPointSelector die Basis-Seitenfläche statt die Feature-Seitenfläche treffen → Punkt GENAU auf Feature-Fläche setzen
