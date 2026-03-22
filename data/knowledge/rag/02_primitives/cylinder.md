# Cylinder — Zylinder erstellen
Tags: zylinder, cylinder, rohr, welle, säule, bolzen, stift, pin, rod, shaft, nabe, hub

## Wann verwenden
- User sagt: "Zylinder", "Welle", "Bolzen", "Stift", "Säule", "Rohr", "Nabe"
- Runde Grundkörper oder Aufsätze
- Basis für Rotoren, Achsen, Buchsen

## CadQuery Code (modulare Funktion)

```python
def make_cylinder(height: float, radius: float,
                  centered: bool = True) -> cq.Workplane:
    """Erstellt einen Zylinder.

    Args:
        height: Höhe in Z-Richtung (mm)
        radius: Radius (mm) — NICHT Durchmesser!
        centered: True = Z-Achse zentriert

    Returns:
        Zylinder, Achse entlang Z.
    """
    return cq.Workplane("XY").cylinder(height, radius,
                                        centered=(True, True, False))


def make_cylinder_at_position(height: float, radius: float,
                               pos_x: float, pos_y: float,
                               pos_z: float) -> cq.Workplane:
    """Erstellt einen Zylinder an bestimmter Position (Zentrum der Basis)."""
    return (cq.Workplane("XY")
            .cylinder(height, radius)
            .translate((pos_x, pos_y, pos_z)))


def add_cylinder_on_face(body: cq.Workplane, face_selector: str,
                         height: float, radius: float) -> cq.Workplane:
    """Fügt zylindrischen Boss auf einer Face hinzu."""
    return (body.faces(face_selector)
            .workplane(centerOption='CenterOfBoundBox')
            .circle(radius)
            .extrude(height))
```

## Parameter-Referenz
| Parameter | Typ | Beschreibung | Default |
|-----------|-----|--------------|---------|
| height | float | Höhe in mm | — |
| radius | float | Radius in mm (NICHT Durchmesser) | — |
| centered | bool/tuple | Zentriert auf Workplane | (True, True, True) |

## Varianten
- `.cylinder(h, r)`: Freistehender Zylinder
- `.circle(r).extrude(h)`: Zylinder auf bestehender Workplane/Face — bevorzugt für Boss/Aufsatz
- `centered=(True, True, False)`: Z beginnt bei Workplane statt zentriert

## Häufige Fehler
1. **Radius vs. Durchmesser**: `.cylinder(20, 10)` → Radius 10 = Durchmesser 20! User sagt oft "Durchmesser 10" → Radius 5
2. **Achsenrichtung**: Zylinder geht immer in Z-Richtung der Workplane. Für liegenden Zylinder: `cq.Workplane("XZ").cylinder(h, r)`
3. **Boss auf Face**: NICHT `.cylinder()` verwenden sondern `.circle(r).extrude(h)` auf der Face-Workplane

## Komposition
- Als Basis (Nabe): Direkt erstellen
- Als Boss auf Platte: `.faces(">Z").workplane().circle(r).extrude(h)`
- Als Welle durch Körper: Separater Body → `.union()` oder `.cut()`

## ★ Stufen-Zylinder (mehrere Zylinder gestapelt)

```python
from cadquery.selectors import NearestToPointSelector

# Beispiel: D20h20 → D40h20 → D20h20
BASE_D, BASE_H = 20.0, 20.0
STEP1_D, STEP1_H = 40.0, 20.0
STEP2_D, STEP2_H = 20.0, 20.0

def make_base() -> cq.Workplane:
    return cq.Workplane("XY").cylinder(BASE_H, BASE_D / 2, centered=(True, True, False))

def add_step_1(body: cq.Workplane) -> cq.Workplane:
    # Erster Aufsatz auf Basis — ">Z" ist eindeutig (nur eine Top-Face)
    return (body.faces(">Z")
            .workplane(centerOption='CenterOfBoundBox')
            .circle(STEP1_D / 2)
            .extrude(STEP1_H))

def add_step_2(body: cq.Workplane) -> cq.Workplane:
    # Zweiter Aufsatz — NearestToPointSelector wegen vorherigem extrude
    # Step1-Top bei Z = BASE_H + STEP1_H = 40
    return (body.faces(NearestToPointSelector((0, 0, BASE_H + STEP1_H)))
            .workplane(centerOption='CenterOfBoundBox')
            .circle(STEP2_D / 2)
            .extrude(STEP2_H))
```

**★ FALSCH — erzeugt `AttributeError: 'tuple' object has no attribute 'clean'`:**
```python
# NIEMALS so:
def add_step_1(body: cq.Workplane) -> cq.Workplane:
    step = cq.Workplane("XY").cylinder(STEP1_H, STEP1_D / 2)  # ❌ neues Workplane
    return body.union(step).clean()                            # ❌ union mit Workplane
```
