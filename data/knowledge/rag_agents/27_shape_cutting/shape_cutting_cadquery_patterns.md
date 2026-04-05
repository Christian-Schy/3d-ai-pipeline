# CadQuery Shape-Cutting Patterns

## Dreieck ausschneiden (triangle_cut)
```python
# Dreieck aus Oberseite einer Box schneiden: Grundseite 20mm, Höhe 15mm, Tiefe 5mm
def cut_triangle(body):
    triangle = (
        body
        .faces(">Z")
        .workplane(centerOption="CenterOfBoundBox")
        .moveTo(-10, 0)
        .lineTo(10, 0)
        .lineTo(0, 15)
        .close()
        .cutBlind(-5)
    ).clean()
    return triangle
```

## Viertelkreis ausschneiden (arc_cut / quarter circle)
```python
# Viertelkreis-Ausschnitt aus Ecke: Radius 15mm, Tiefe 10mm, durchgehend
def cut_quarter_circle(body):
    result = (
        body
        .faces(">Z")
        .workplane(centerOption="CenterOfBoundBox")
        .center(25, 15)  # Ecke der Box
        .moveTo(0, 0)
        .radiusArc((-15, 0), 15)  # Viertelkreisbogen R15
        .lineTo(0, 0)
        .close()
        .cutBlind(-10)
    ).clean()
    return result
```

## Halbkreis ausschneiden (arc_cut / semicircle)
```python
# Halbkreis an der Kante: Radius 12mm, durchgehend
def cut_semicircle(body):
    result = (
        body
        .faces(">Z")
        .workplane(centerOption="CenterOfBoundBox")
        .center(0, 20)  # Kante der Box
        .moveTo(-12, 0)
        .radiusArc((12, 0), 12)  # Halbkreisbogen
        .lineTo(-12, 0)
        .close()
        .cutThruAll()
    ).clean()
    return result
```

## Bogenförmiger Ausschnitt mit sagittaArc
```python
# Flacher Bogenausschnitt: Breite 30mm, Pfeilhöhe 8mm, Tiefe 5mm
def cut_sagitta_arc(body):
    result = (
        body
        .faces(">Z")
        .workplane(centerOption="CenterOfBoundBox")
        .moveTo(-15, 0)
        .sagittaArc((15, 0), 8)  # Bogen mit Pfeilhöhe 8mm
        .lineTo(-15, 0)
        .close()
        .cutBlind(-5)
    ).clean()
    return result
```

## Custom Shape hinzufügen (custom_shape_add)
```python
# L-förmiges Profil extrudieren und auf Box setzen
def add_l_shape(body):
    l_profile = (
        body
        .faces(">Z")
        .workplane(centerOption="CenterOfBoundBox")
        .moveTo(0, 0)
        .lineTo(20, 0)
        .lineTo(20, 5)
        .lineTo(5, 5)
        .lineTo(5, 15)
        .lineTo(0, 15)
        .close()
        .extrude(10)
    ).clean()
    return l_profile
```

## Custom Shape ausschneiden (custom_shape_cut)
```python
# T-förmige Nut von oben in eine Box
def cut_t_slot(body):
    result = (
        body
        .faces(">Z")
        .workplane(centerOption="CenterOfBoundBox")
        .moveTo(-10, 0)
        .lineTo(10, 0)
        .lineTo(10, 3)
        .lineTo(3, 3)
        .lineTo(3, 12)
        .lineTo(-3, 12)
        .lineTo(-3, 3)
        .lineTo(-10, 3)
        .close()
        .cutBlind(-8)
    ).clean()
    return result
```

## Polyline-basierter Ausschnitt
```python
# Beliebiges Polygon aus Vertices-Liste schneiden
def cut_polygon(body, vertices, depth):
    """vertices = [(x1,y1), (x2,y2), ...] — geschlossenes Polygon"""
    wp = (
        body
        .faces(">Z")
        .workplane(centerOption="CenterOfBoundBox")
    )
    sketch = wp.moveTo(*vertices[0])
    for v in vertices[1:]:
        sketch = sketch.lineTo(*v)
    result = sketch.close().cutBlind(-depth).clean()
    return result
```

## Keilform ausschneiden (wedge cut)
```python
# Keil von der Seite: Breite 30mm, Höhe 20mm, Tiefe 15mm
def cut_wedge(body):
    result = (
        body
        .faces(">X")
        .workplane(centerOption="CenterOfBoundBox")
        .moveTo(-15, -10)
        .lineTo(15, -10)
        .lineTo(0, 10)
        .close()
        .cutBlind(-15)
    ).clean()
    return result
```

## Abgerundete Ecke (Eckenverrundung als Shape)
```python
# Ecke einer Box abrunden mit Viertelkreis-Ausschnitt
# Anstatt fillet() — stabiler über Shape-Cut
def round_corner(body, radius=10):
    result = (
        body
        .faces(">Z")
        .workplane(centerOption="CenterOfBoundBox")
        .center(25, 15)  # Ecke positionieren (halbe Box-Breite, halbe Box-Tiefe)
        .moveTo(0, 0)
        .lineTo(-radius, 0)
        .radiusArc((0, -radius), radius)
        .lineTo(0, 0)
        .close()
        .cutThruAll()
    ).clean()
    return result
```

## Diagonale Nut (schräge Nut / diagonal groove)
```python
# Diagonale Nut von Ecke zu Ecke auf der Oberseite einer 60mm Box
# Breite 5mm, Tiefe 5mm, verläuft diagonal von links-vorne nach rechts-hinten
def cut_diagonal_groove(body):
    half_w = 2.5  # halbe Nutbreite
    # Die Nut verläuft diagonal — definiere ein Parallelogramm entlang der Diagonale
    result = (
        body
        .faces(">Z")
        .workplane(centerOption="CenterOfBoundBox")
        .moveTo(-30 - half_w, -30)      # Start: links-vorne (mit Breiten-Offset)
        .lineTo(-30 + half_w, -30)       # Start: rechte Seite der Nut
        .lineTo(30 + half_w, 30)         # Ende: rechts-hinten (mit Breiten-Offset)
        .lineTo(30 - half_w, 30)         # Ende: linke Seite der Nut
        .close()
        .cutBlind(-5)
    ).clean()
    return result
```

## Diagonale Nut mit Winkel (angled groove)
```python
# Nut im 45-Grad-Winkel auf der Rückseite (face >Y)
# Breite 4mm, Tiefe 3mm
import math
def cut_angled_groove(body, width=4, depth=3, angle_deg=45):
    half_w = width / 2
    angle_rad = math.radians(angle_deg)
    # Nut-Richtungsvektor
    dx = math.cos(angle_rad)
    dy = math.sin(angle_rad)
    # Senkrechter Vektor für Breite
    nx = -dy * half_w
    ny = dx * half_w
    # Start- und Endpunkte (über volle Face-Diagonale)
    length = 40  # halbe Diagonale
    result = (
        body
        .faces(">Y")
        .workplane(centerOption="CenterOfBoundBox")
        .moveTo(-dx*length + nx, -dy*length + ny)
        .lineTo(-dx*length - nx, -dy*length - ny)
        .lineTo(dx*length - nx, dy*length - ny)
        .lineTo(dx*length + nx, dy*length + ny)
        .close()
        .cutBlind(-depth)
    ).clean()
    return result
```

## WICHTIGE REGELN für Shape-Cutting:
1. IMMER `.close()` vor `.cutBlind()` oder `.cutThruAll()` — offene Pfade crashen!
2. `radiusArc((endX, endY), radius)` — positiver Radius = Bogen links, negativer = rechts
3. `sagittaArc((endX, endY), sagitta)` — sagitta = Pfeilhöhe des Bogens
4. `.moveTo()` setzt den Startpunkt, `.lineTo()` zieht Linien
5. Für durchgehende Schnitte: `.cutThruAll()` statt `.cutBlind(-tiefe)`
6. Bei `.center(x, y)` vor dem Pfad: verschiebt den Ursprung relativ zum Face-Zentrum
7. Nach `.cut()` und `.union()` IMMER `.clean()` aufrufen
8. Vertices im Uhrzeigersinn oder gegen Uhrzeigersinn — Hauptsache konsistent
9. Für Custom Shapes als Add: `.extrude(höhe)` statt `.cutBlind()`
