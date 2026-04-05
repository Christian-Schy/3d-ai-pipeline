# CadQuery Zylinder-Patterns

## Vollzylinder erstellen
```python
# Einfacher Zylinder: Durchmesser 30mm, Höhe 50mm
def build_cylinder():
    result = (
        cq.Workplane("XY")
        .circle(15)  # Radius = Durchmesser/2
        .extrude(50)
    )
    return result
```

## Hohlzylinder (Rohr)
```python
# Rohr: Außendurchmesser 40mm, Innendurchmesser 30mm, Höhe 60mm
def build_tube():
    outer = (
        cq.Workplane("XY")
        .circle(20)  # Außenradius
        .extrude(60)
    )
    inner = (
        cq.Workplane("XY")
        .circle(15)  # Innenradius
        .extrude(60)
    )
    result = outer.cut(inner).clean()
    return result
```

## Zylinder mit Bohrung von oben
```python
# Zylinder D40 H30 mit Bohrung D10 von oben, 20mm tief
def build_cylinder_with_hole():
    base = (
        cq.Workplane("XY")
        .circle(20)
        .extrude(30)
    )
    result = (
        base
        .faces(">Z")
        .workplane(centerOption="CenterOfBoundBox")
        .circle(5)
        .cutBlind(-20)
    ).clean()
    return result
```

## Zylinder auf einer Box positionieren
```python
# Zylinder D20 H15 zentriert auf Box-Oberseite
def build_box():
    return cq.Workplane("XY").box(50, 50, 10)

def build_cylinder_on_box(box):
    result = (
        box
        .faces(">Z")
        .workplane(centerOption="CenterOfBoundBox")
        .circle(10)
        .extrude(15)
    ).clean()
    return result
```

## Zylinder als Subtract (zylindrische Tasche)
```python
# Zylindrische Tasche D25 Tiefe 8mm von oben in Box
def build_pocket(box):
    result = (
        box
        .faces(">Z")
        .workplane(centerOption="CenterOfBoundBox")
        .circle(12.5)
        .cutBlind(-8)
    ).clean()
    return result
```

## Zylinder seitlich an Box
```python
# Zylinder D20 H40 an der rechten Seite einer Box
def build_side_cylinder(box):
    result = (
        box
        .faces(">X")
        .workplane(centerOption="CenterOfBoundBox")
        .circle(10)
        .extrude(40)
    ).clean()
    return result
```

## WICHTIGE REGELN für Zylinder:
1. IMMER `circle(radius)` verwenden, NICHT `circle(diameter)`! Radius = Durchmesser/2
2. Zylinder mit `.circle().extrude()`, NICHT mit `.cylinder()`
3. Bei Positionierung auf Face: IMMER `centerOption="CenterOfBoundBox"`
4. Nach `.union()` und `.cut()` IMMER `.clean()` aufrufen
5. Hohlzylinder: Erst äußeren Zylinder, dann inneren ausschneiden
6. Zylindrische Bohrung: `.circle(radius).cutBlind(-tiefe)`
