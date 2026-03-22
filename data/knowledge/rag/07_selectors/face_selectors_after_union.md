# Face Selectors After Union — ★ Flächen-Auswahl nach Boolean-Operationen
Tags: union, boolean, face_nach_union, mehrdeutig, falsche_face, selector_problem, cut

## Wann verwenden
- IMMER wenn nach `.union()` oder `.cut()` ein Feature platziert wird
- Wenn `>Z` plötzlich die falsche Fläche trifft
- Das häufigste Problem in der gesamten Pipeline

## Das Problem

```python
# Basis: 100x100x20 Platte
base = cq.Workplane("XY").box(100, 100, 20, centered=(True, True, False))
# Steg: 20x100x30 oben rechts
steg = cq.Workplane("XY").box(20, 100, 30).translate((40, 0, 35))
body = base.union(steg).clean()

# PROBLEM: >Z trifft jetzt die Steg-Oberseite (Z=50), NICHT die Basis-Oberseite (Z=20)!
# Wenn wir eine Bohrung in die BASIS-Oberseite wollen:
body.faces(">Z").workplane().hole(10)  # FALSCH — bohrt in den Steg!
```

## CadQuery Code — Lösungsstrategien

```python
from cadquery.selectors import (
    NearestToPointSelector,
    DirectionNthSelector
)

# === Strategie 1: NearestToPointSelector (EMPFOHLEN) ===
def feature_on_base_top(body: cq.Workplane, base_center_x: float,
                         base_center_y: float, base_top_z: float) -> cq.Workplane:
    """Selektiert die Basis-Oberseite nach einer Union.

    Args:
        base_center_x/y: Mitte der Basis (oft 0, 0)
        base_top_z: Z-Höhe der Basis-Oberseite
    """
    return body.faces(NearestToPointSelector((base_center_x, base_center_y, base_top_z)))


# === Strategie 2: DirectionNthSelector ===
def select_second_highest_face(body: cq.Workplane) -> cq.Workplane:
    """Wählt die zweithöchste Face — nützlich bei Stufen.

    n=0 → höchste (Steg-Top), n=1 → zweithöchste (Basis-Top)
    """
    return body.faces(DirectionNthSelector((0, 0, 1), 1))


# === Strategie 3: Bohrung VOR Union platzieren ===
def feature_before_union(base: cq.Workplane, steg: cq.Workplane,
                          hole_diameter: float) -> cq.Workplane:
    """Features auf der Basis platzieren BEVOR der Steg vereinigt wird."""
    base_with_hole = (base.faces(">Z")
                      .workplane(centerOption='CenterOfBoundBox')
                      .hole(hole_diameter))
    return base_with_hole.union(steg).clean()


# === VOLLSTÄNDIGES BEISPIEL: Platte + Steg + Bohrung in Basis ===
def example_union_then_hole():
    # 1. Basis erstellen
    base = cq.Workplane("XY").box(100, 100, 20, centered=(True, True, False))
    # Basis-Top ist bei Z=20

    # 2. Steg erstellen und vereinigen
    steg = cq.Workplane("XY").box(20, 100, 30).translate((40, 0, 35))
    body = base.union(steg).clean()

    # 3. Bohrung in Basis-Oberseite (NICHT in Steg)
    # Punkt nahe der Basis-Mitte bei Z=20 → trifft Basis-Top
    result = (body.faces(NearestToPointSelector((0, 0, 20)))
              .workplane(centerOption='CenterOfBoundBox')
              .hole(10))
    return result


# === VOLLSTÄNDIGES BEISPIEL: Bohrung IN Steg nach Union ===
def example_hole_in_steg():
    base = cq.Workplane("XY").box(100, 100, 20, centered=(True, True, False))
    steg = cq.Workplane("XY").box(20, 100, 30).translate((40, 0, 35))
    body = base.union(steg).clean()

    # Steg-Oberseite ist bei Z=50, Zentrum bei X=40
    result = (body.faces(NearestToPointSelector((40, 0, 50)))
              .workplane(centerOption='CenterOfBoundBox')
              .hole(8))
    return result
```

## Entscheidungsbaum: Welche Strategie?

```
Feature auf einer Face nach Union?
│
├── Weißt du die Z-Höhe und XY-Position der Ziel-Face?
│   └── JA → NearestToPointSelector((x, y, z))  ★ EMPFOHLEN
│
├── Willst du die N-te Stufe von oben/unten?
│   └── JA → DirectionNthSelector((0,0,1), n)
│
├── Ist die Reihenfolge flexibel?
│   └── JA → Feature VOR der Union platzieren
│
└── Keine der obigen?
    └── Faces als Liste untersuchen: body.faces("+Z").vals()
```

## Häufige Fehler
1. **★★★ `>Z` nach Union**: Trifft IMMER die höchste Face — bei Stufen-Teilen ist das der Aufsatz, nicht die Basis
2. **NearestToPointSelector Punkt zu ungenau**: Den Punkt möglichst NAHE am Zentrum der Ziel-Face setzen
3. **Vergessen dass `.clean()` Faces ändern kann**: Nach `.clean()` können Faces zusammengefasst oder aufgeteilt werden
4. **`+Z` statt `>Z` für "alle Top-Faces"**: `+Z` gibt alle nach oben zeigenden Faces — kann bei Stufen mehrere sein

## Komposition
- Bohrung in Basis nach Union mit Steg: `NearestToPointSelector((0, 0, basis_top_z))`
- Bohrung im Steg nach Union: `NearestToPointSelector((steg_center_x, steg_center_y, steg_top_z))`
- Lochkreis auf Basis, nicht auf Steg: Feature VOR Union platzieren ODER NearestToPointSelector
