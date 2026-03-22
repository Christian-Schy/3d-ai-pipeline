# Face Selection After Union (Komposition) — ★ Richtige Face nach Boolean-Ops
Tags: face_nach_union, komposition, richtige_face, union_face, boolean_face, target_face

## Wann verwenden
- Nach JEDER Union: Welche Face soll das nächste Feature bekommen?
- KRITISCHSTES Kompositions-Problem — häufigste Fehlerquelle

## Entscheidungsmatrix

```
Situation                                  → Lösung
─────────────────────────────────────────────────────────────
Feature auf BASIS nach Union               → NearestToPointSelector((0, 0, base_top_z))
Feature auf AUFSATZ nach Union             → NearestToPointSelector((aufsatz_x, aufsatz_y, aufsatz_top_z))
Feature auf SEITENFLÄCHE nach Union        → NearestToPointSelector((face_x, center_y, center_z))
Feature auf EINZIGER Top-Face (vor Union)  → faces(">Z") ist OK
Feature auf Taschenboden nach Cut          → NearestToPointSelector((0, 0, boden_z))
                                             ODER DirectionNthSelector((0,0,1), 1)
```

## CadQuery Code — Rezepte

```python
from cadquery.selectors import NearestToPointSelector, DirectionNthSelector

# ═══════════════════════════════════════════════════════
# REZEPT 1: Bohrung in Basis-Oberseite NACH Union mit Steg
# ═══════════════════════════════════════════════════════

def recipe_hole_in_base_after_union():
    base = cq.Workplane("XY").box(100, 100, 20, centered=(True, True, False))
    steg = cq.Workplane("XY").box(20, 40, 30).translate((30, 0, 35))
    body = base.union(steg).clean()

    # Basis-Top: Z=20, Zentrum bei (0, 0)
    # Steg-Top: Z=50, Zentrum bei (30, 0)
    # >Z → trifft Z=50 (Steg!) FALSCH für Basis

    # RICHTIG: Punkt auf Basis-Top, ABSEITS vom Steg
    return (body.faces(NearestToPointSelector((-20, 0, 20)))
            .workplane(centerOption='CenterOfBoundBox')
            .hole(10))


# ═══════════════════════════════════════════════════════
# REZEPT 2: Lochkreis auf Aufsatz NACH Union
# ═══════════════════════════════════════════════════════

def recipe_bolt_circle_on_boss_after_union():
    import math
    base = cq.Workplane("XY").box(120, 120, 10, centered=(True, True, False))
    boss = cq.Workplane("XY").cylinder(15, 30).translate((0, 0, 17.5))
    body = base.union(boss).clean()

    # Boss-Top: Z=25, Zentrum bei (0, 0)
    r = 20
    n = 6
    points = [(r * math.cos(2 * math.pi * i / n),
               r * math.sin(2 * math.pi * i / n)) for i in range(n)]

    return (body.faces(NearestToPointSelector((0, 0, 25)))
            .workplane(centerOption='CenterOfBoundBox')
            .pushPoints(points).hole(6.6))


# ═══════════════════════════════════════════════════════
# REZEPT 3: Feature auf zweithöchster Stufe
# ═══════════════════════════════════════════════════════

def recipe_feature_on_step():
    base = cq.Workplane("XY").box(100, 100, 10, centered=(True, True, False))
    step1 = cq.Workplane("XY").box(70, 70, 10).translate((0, 0, 15))
    step2 = cq.Workplane("XY").box(40, 40, 10).translate((0, 0, 25))
    body = base.union(step1).clean().union(step2).clean()

    # Stufen: Z=10 (Basis), Z=20 (Step1), Z=30 (Step2)
    # Bohrung auf Step1 (Z=20):
    return (body.faces(NearestToPointSelector((0, 0, 20)))
            .workplane(centerOption='CenterOfBoundBox')
            .hole(8))


# ═══════════════════════════════════════════════════════
# REZEPT 4: Vermeidungsstrategie — Features VOR Union
# ═══════════════════════════════════════════════════════

def recipe_features_before_union():
    """Beste Strategie: Features auf Basis bohren BEVOR Union."""
    base = cq.Workplane("XY").box(100, 100, 20, centered=(True, True, False))

    # Bohrungen JETZT — >Z ist noch eindeutig!
    base = (base.faces(">Z")
            .workplane(centerOption='CenterOfBoundBox')
            .pushPoints([(30, 30), (-30, 30), (30, -30), (-30, -30)])
            .hole(5))

    # DANACH erst Union
    steg = cq.Workplane("XY").box(20, 80, 25).translate((0, 0, 32.5))
    body = base.union(steg).clean()

    return body
```

## NearestToPointSelector — Punkt-Berechnung Quick Reference

```
Feature-Art         | Top-Face Punkt                    | Seiten-Face Punkt
────────────────────|───────────────────────────────────|──────────────────────
Box bei (tx, ty)    | (tx, ty, base_h + feat_h)         | (tx ± feat_w/2, ty, base_h + feat_h/2)
Zylinder bei (tx,ty)| (tx, ty, base_h + feat_h)         | (tx ± feat_r, ty, base_h + feat_h/2)
Basis-Oberseite     | (0, 0, base_h)                    | (±base_w/2, 0, base_h/2)
Taschenboden        | (pocket_x, pocket_y, base_h - depth) | —
```

## Häufige Fehler
1. **★★★ >Z nach Union**: Trifft IMMER die globale Höchste — fast nie was man will
2. **Punkt auf falscher Face**: Wenn Basis und Feature gleiche X/Y haben → Z-Koordinate entscheidet
3. **Punkt zu weit weg**: NearestToPointSelector nimmt die NÄCHSTE Face — Punkt muss nahe am Zentrum der Ziel-Face sein
4. **Vergessen dass .clean() Faces zusammenführt**: Nach clean können benachbarte koplanare Faces eine werden
