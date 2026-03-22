# Feature on Feature — ★ Feature auf einem anderen Feature platzieren
Tags: feature_auf_feature, verschachtelt, nested, steg_auf_steg, secondary, zweites_feature

## Wann verwenden
- Ein Feature (Bohrung, Boss, Tasche) soll auf einem ANDEREN Feature sitzen
- Nicht auf der Basis, sondern auf einem zuvor erstellten Aufsatz
- ★ KRITISCH: Häufigstes Kompositions-Problem

## Das Problem

```python
# Basis + Steg
base = cq.Workplane("XY").box(100, 100, 20, centered=(True, True, False))
steg = cq.Workplane("XY").box(30, 30, 15).translate((25, 25, 27.5))
body = base.union(steg).clean()

# JETZT: Boss auf dem Steg platzieren
# FALSCH: >Z trifft die Steg-Oberseite nur wenn sie die HÖCHSTE ist
# RICHTIG: NearestToPointSelector mit Steg-Zentrum
```

## CadQuery Code (modulare Funktion)

```python
from cadquery.selectors import NearestToPointSelector

def add_feature_on_feature(body: cq.Workplane,
                            parent_center: tuple,
                            feature_type: str = "hole",
                            **params) -> cq.Workplane:
    """Platziert ein Feature auf einem bestehenden Feature.

    Args:
        parent_center: (x, y, z) Zentrum der Ziel-Face des Parent-Features
        feature_type: "hole", "boss_rect", "boss_round", "pocket"
        **params: Feature-spezifische Parameter
    """
    wp = (body.faces(NearestToPointSelector(parent_center))
          .workplane(centerOption='CenterOfBoundBox'))

    if feature_type == "hole":
        d = params.get('diameter', 10)
        depth = params.get('depth', None)
        ox = params.get('offset_x', 0)
        oy = params.get('offset_y', 0)
        wp = wp.center(ox, oy)
        return wp.hole(d, depth) if depth else wp.hole(d)

    elif feature_type == "boss_round":
        r = params.get('radius', 5)
        h = params.get('height', 10)
        ox = params.get('offset_x', 0)
        oy = params.get('offset_y', 0)
        return wp.center(ox, oy).circle(r).extrude(h)

    elif feature_type == "boss_rect":
        w = params.get('width', 10)
        l = params.get('length', 10)
        h = params.get('height', 10)
        ox = params.get('offset_x', 0)
        oy = params.get('offset_y', 0)
        return wp.center(ox, oy).rect(w, l).extrude(h)

    elif feature_type == "pocket":
        w = params.get('width', 10)
        l = params.get('length', 10)
        d = params.get('depth', 5)
        ox = params.get('offset_x', 0)
        oy = params.get('offset_y', 0)
        return wp.center(ox, oy).rect(w, l).cutBlind(-d)


# ★ VOLLSTÄNDIGES BEISPIEL: Platte → Steg → Bohrung im Steg
def example_nested_features():
    # 1. Basis: 100x100x20
    base = cq.Workplane("XY").box(100, 100, 20, centered=(True, True, False))
    # Basis-Top bei Z=20

    # 2. Steg: 30x30x15, oben rechts hinten
    steg = cq.Workplane("XY").box(30, 30, 15).translate((25, -25, 27.5))
    body = base.union(steg).clean()
    # Steg-Top bei Z=35, Zentrum bei (25, -25)

    # 3. Bohrung IM STEG (nicht in der Basis!)
    result = add_feature_on_feature(
        body,
        parent_center=(25, -25, 35),  # Steg-Top-Zentrum
        feature_type="hole",
        diameter=8
    )
    return result


# ★ VOLLSTÄNDIGES BEISPIEL: Boss auf Boss
def example_boss_on_boss():
    # 1. Basis
    base = cq.Workplane("XY").box(80, 80, 10, centered=(True, True, False))

    # 2. Großer Boss
    body = (base.faces(">Z")
            .workplane(centerOption='CenterOfBoundBox')
            .circle(20).extrude(15))
    # Boss-Top bei Z=25

    # 3. Kleiner Boss auf großem Boss
    result = (body.faces(NearestToPointSelector((0, 0, 25)))
              .workplane(centerOption='CenterOfBoundBox')
              .circle(8).extrude(10))
    # Kleiner-Boss-Top bei Z=35
    return result
```

## Berechnung von parent_center

```
parent_center_z = basis_z + parent_feature_z
parent_center_x = parent_translate_x
parent_center_y = parent_translate_y
```

Beispiel: Basis 20mm hoch, Steg 15mm hoch bei X=25, Y=-25:
→ Steg-Top: parent_center = (25, -25, 20 + 15) = (25, -25, 35)

## Häufige Fehler
1. **★★★ >Z statt NearestToPointSelector**: Nach Union trifft >Z die höchste Face — bei Stufen ist das der Aufsatz, nicht die Basis
2. **parent_center Z falsch berechnet**: Z = Summe aller darunterliegenden Höhen, nicht nur die Feature-Höhe
3. **CenterOfBoundBox vergessen**: Ohne das liegt der Workplane-Ursprung am projizierten globalen Ursprung
4. **Feature zu groß für Parent**: Wenn das Feature größer als die Parent-Face ist → übersteht, kann zu ungültiger Geometrie führen
