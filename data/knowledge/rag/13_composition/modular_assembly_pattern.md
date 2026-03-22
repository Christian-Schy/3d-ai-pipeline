# Modular Assembly Pattern — ★ Referenz für modularen Code-Aufbau
Tags: modular, assembly, assemble, pattern, zusammenbau, referenz, template, skeleton

## Wann verwenden
- IMMER — dies ist das Standard-Pattern für JEDEN generierten Code
- Der Function Decomposer erzeugt ein Skeleton nach diesem Muster
- Der Coder füllt die Funktionen aus

## CadQuery Code — Das Standard-Template

```python
import cadquery as cq
from cadquery.selectors import NearestToPointSelector
import math

OUTPUT_PATH = "output.stl"

# ============================================================
# PARAMETER (alle Maße in mm)
# ============================================================
BASE_W, BASE_L, BASE_H = 100.0, 80.0, 15.0
STEG_W, STEG_L, STEG_H = 10.0, 80.0, 20.0
BOSS_R, BOSS_H = 12.0, 10.0
HOLE_D_CORNERS = 5.0
HOLE_D_BOSS = 8.0
HOLE_INSET = 10.0


# ============================================================
# FEATURE-FUNKTIONEN (eine pro Feature)
# ============================================================

def make_base() -> cq.Workplane:
    """Basis-Platte erstellen.

    Erstellt: Box 100×80×15mm
    Position: Zentriert in X/Y, Z von 0 bis 15
    """
    return cq.Workplane("XY").box(BASE_W, BASE_L, BASE_H,
                                   centered=(True, True, False))


def drill_corner_holes(body: cq.Workplane) -> cq.Workplane:
    """4 Eckbohrungen in die Basis.

    Parent: base (>Z Face, Z=15)
    Bohrungen: ∅5mm, durchgehend, 10mm vom Rand
    HINWEIS: VOR Union mit Steg/Boss ausführen!
    """
    hw = BASE_W / 2 - HOLE_INSET
    hl = BASE_L / 2 - HOLE_INSET
    points = [(hw, hl), (-hw, hl), (hw, -hl), (-hw, -hl)]
    return (body.faces(">Z")
            .workplane(centerOption='CenterOfBoundBox')
            .pushPoints(points)
            .hole(HOLE_D_CORNERS))


def add_steg_rechts(body: cq.Workplane) -> cq.Workplane:
    """Steg auf der rechten Seite der Basis.

    Feature: Box 10×80×20mm
    Position: Bündig rechts (X=45), auf der Basis (Z=25)
    Boolean: Union + clean
    """
    steg_x = BASE_W / 2 - STEG_W / 2   # = 45
    steg_z = BASE_H + STEG_H / 2        # = 25
    steg = (cq.Workplane("XY")
            .box(STEG_W, STEG_L, STEG_H)
            .translate((steg_x, 0, steg_z)))
    return body.union(steg).clean()


def add_boss_mitte(body: cq.Workplane) -> cq.Workplane:
    """Zylindrischer Boss mittig auf der Basis.

    Feature: Zylinder ∅24, h=10
    Position: Mitte (X=0, Y=0), auf der Basis (Z=20)
    Boolean: Union + clean
    """
    boss_z = BASE_H + BOSS_H / 2        # = 20
    boss = (cq.Workplane("XY")
            .cylinder(BOSS_H, BOSS_R)
            .translate((0, 0, boss_z)))
    return body.union(boss).clean()


def drill_boss_hole(body: cq.Workplane) -> cq.Workplane:
    """Durchgangsbohrung im Boss.

    Parent: boss_mitte (Top-Face bei Z=25)
    Bohrung: ∅8mm, durchgehend
    Selektor: NearestToPointSelector — Boss-Top bei (0, 0, 25)
    """
    boss_top_z = BASE_H + BOSS_H        # = 25
    return (body.faces(NearestToPointSelector((0, 0, boss_top_z)))
            .workplane(centerOption='CenterOfBoundBox')
            .hole(HOLE_D_BOSS))


# ============================================================
# ASSEMBLY (baut alles zusammen in korrekter Reihenfolge)
# ============================================================

def assemble() -> cq.Workplane:
    """Hauptfunktion: Baut das Teil Schritt für Schritt.

    Build Order:
    1. make_base()           — Grundkörper
    2. drill_corner_holes()  — Subtraktiv auf Basis (VOR Union)
    3. add_steg_rechts()     — Additiv (Union)
    4. add_boss_mitte()      — Additiv (Union)
    5. drill_boss_hole()     — Subtraktiv auf Feature (NACH Union)
    """
    result = make_base()
    result = drill_corner_holes(result)
    result = add_steg_rechts(result)
    result = add_boss_mitte(result)
    result = drill_boss_hole(result)
    return result


# ============================================================
# EXPORT
# ============================================================
result = assemble()
cq.exporters.export(result, OUTPUT_PATH)
```

## Struktur-Regeln

### 1. Parameter-Block oben
- ALLE Maße als Konstanten am Anfang
- Keine Magic Numbers im Code
- Erleichtert spätere Modifikationen

### 2. Eine Funktion pro Feature
- Jede Funktion hat einen klaren Docstring
- Docstring enthält: Was, Position, Parent, Boolean-Typ
- Funktion nimmt `body` entgegen und gibt `body` zurück
- Ausnahme: `make_base()` nimmt nichts und gibt den Grundkörper zurück

### 3. Build-Reihenfolge in assemble()
```
1. Basis erstellen
2. Subtraktive Features auf Basis (>Z ist noch eindeutig)
3. Additive Features (Union) — eines nach dem anderen mit .clean()
4. Subtraktive Features auf additiven Features (NearestToPointSelector)
5. Fillets / Chamfers (IMMER am Ende)
```

### 4. Face-Selektion
- Auf der Basis (vor Union): `>Z`, `>X` etc. sind sicher
- Nach Union: IMMER `NearestToPointSelector((x, y, z))`
- IMMER `centerOption='CenterOfBoundBox'`

### 5. Boolean-Hygiene
- `.clean()` nach JEDER Union/Cut
- Nie zwei Booleans ohne `.clean()` dazwischen

## Für Modifikationen
Der modulare Aufbau ermöglicht gezielte Änderungen:
- "Mach die Bohrung größer" → nur `HOLE_D_BOSS` ändern
- "Steg soll 30mm hoch sein" → nur `STEG_H` ändern
- "Füge einen zweiten Boss hinzu" → neue Funktion + in assemble() einfügen

## Häufige Fehler
1. **Funktionen nicht in der richtigen Reihenfolge**: Build Order in assemble() muss Dependencies respektieren
2. **Parameter nicht oben definiert**: Maße direkt im Code → schwer zu ändern
3. **Keine Docstrings**: Ohne Docstrings weiß der Modification Guard nicht welches Feature gemeint ist
4. **result nicht durchreichen**: `result = func(result)` — Variable muss aktualisiert werden
