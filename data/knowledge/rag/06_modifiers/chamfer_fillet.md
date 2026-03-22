# Chamfer und Fillet (Fase / Verrundung)

## Kritische Regeln
- `.chamfer(size)` und `.fillet(size)` werden DIREKT auf dem Workplane aufgerufen — KEIN `.faces()` davor
- `.edges()` wählt zuerst die Kanten aus, DANN kommt `.chamfer()` oder `.fillet()`
- `.chamfer()` und `.fillet()` nehmen KEINEN `face` oder `workplane` — nur die Kantenauswahl davor

## Alle 12 Kanten eines Quaders — chamfer

```python
def apply_chamfer_all_edges(body: cq.Workplane) -> cq.Workplane:
    """Fase an allen Kanten."""
    return body.edges().chamfer(CHAMFER_SIZE)
```

## Alle Kanten — fillet

```python
def apply_fillet_all_edges(body: cq.Workplane) -> cq.Workplane:
    """Verrundung an allen Kanten."""
    return body.edges().fillet(FILLET_RADIUS)
```

## Nur obere Kanten (Z-Richtung)

```python
def apply_chamfer_top(body: cq.Workplane) -> cq.Workplane:
    """Fase nur an den oberen horizontalen Kanten."""
    return body.edges(">Z").chamfer(CHAMFER_SIZE)
```

## Nur vertikale Kanten

```python
def apply_fillet_vertical(body: cq.Workplane) -> cq.Workplane:
    """Verrundung nur an den 4 vertikalen Kanten."""
    return body.edges("|Z").fillet(FILLET_RADIUS)
```

## Box direkt mit Chamfer erstellen (einfachste Variante)

```python
def make_base_with_chamfer() -> cq.Workplane:
    """Quader mit Fase an allen Kanten."""
    return (
        cq.Workplane("XY")
        .box(LENGTH, WIDTH, HEIGHT)
        .edges()
        .chamfer(CHAMFER_SIZE)
    )
```

## ANTI-PATTERNS (SO NICHT):

```python
# ❌ FALSCH: chamfer braucht kein workplane
body.faces(">Z").workplane().chamfer(2)

# ❌ FALSCH: chamfer ist keine Boolean-Op, kein .clean() nötig
body.edges().chamfer(2).clean()

# ❌ FALSCH: centered gehört zu .box(), nicht zu Workplane()
cq.Workplane("XY", centered=True).box(30, 30, 30)
# ✅ RICHTIG:
cq.Workplane("XY").box(30, 30, 30, centered=True)

# ❌ FALSCH: chamfer ohne .edges()
body.chamfer(2)
# ✅ RICHTIG:
body.edges().chamfer(2)

# ❌ FALSCH: fillet ohne .edges()
body.fillet(2)
# ✅ RICHTIG:
body.edges().fillet(2)
```

## Kanten nach Typ auswählen

```python
# Alle horizontalen Kanten (parallel zu XY-Ebene)
body.edges("not |Z").chamfer(size)

# Nur die 4 oberen Eckkanten
body.edges(">Z").chamfer(size)

# Nur die 4 unteren Eckkanten
body.edges("<Z").chamfer(size)

# Längste Kanten (bei unterschiedlichen Längen)
body.edges(cq.selectors.LengthNthSelector(-1)).chamfer(size)
```

## Vollständiges Beispiel: 30mm Würfel mit 2mm Fase

```python
import cadquery as cq

CUBE_SIZE = 30.0
CHAMFER_SIZE = 2.0
OUTPUT_PATH = "output.stl"


def make_base_cube() -> cq.Workplane:
    """30x30x30mm Würfel."""
    return cq.Workplane("XY").box(CUBE_SIZE, CUBE_SIZE, CUBE_SIZE)


def apply_chamfer_all_edges(body: cq.Workplane) -> cq.Workplane:
    """2mm Fase an allen 12 Kanten."""
    return body.edges().chamfer(CHAMFER_SIZE)


def assemble() -> cq.Workplane:
    result = make_base_cube()
    result = apply_chamfer_all_edges(result)
    return result


result = assemble()
cq.exporters.export(result, OUTPUT_PATH)
```
