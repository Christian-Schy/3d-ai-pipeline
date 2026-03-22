# Multi Feature Positioning — Mehrere Features korrekt positionieren
Tags: mehrere_features, multi, positioning, reihenfolge, koordination, komplex

## Wann verwenden
- 3+ Features auf einem Körper
- Features die voneinander abhängen (Feature B auf Feature A)
- Komplexe Teile mit Stegen, Bohrungen, Taschen

## CadQuery Code — Systematischer Aufbau

```python
from cadquery.selectors import NearestToPointSelector

def build_complex_part():
    """Systematischer Aufbau mit Feature-Tracking.

    Teil: 100x80x15 Platte
    + Steg 10x80x20 rechts
    + Boss ∅20, h=10 links-mitte
    + 4 Eckbohrungen ∅5 in Basis
    + Bohrung ∅8 im Boss
    + Querbohrung ∅6 im Steg
    """

    # === Feature-Positionen vorberechnen ===
    base_w, base_l, base_h = 100, 80, 15

    steg_w, steg_l, steg_h = 10, 80, 20
    steg_x = base_w / 2 - steg_w / 2       # 45: bündig rechts
    steg_z = base_h + steg_h / 2            # 25: auf der Basis

    boss_r = 10
    boss_h_val = 10
    boss_x = -20                             # 20mm links von Mitte
    boss_z = base_h + boss_h_val / 2        # 20: auf der Basis

    # === 1. Basis ===
    result = cq.Workplane("XY").box(base_w, base_l, base_h,
                                     centered=(True, True, False))

    # === 2. Eckbohrungen in Basis (VOR Union!) ===
    inset = 10
    corner_points = [
        ( base_w / 2 - inset,  base_l / 2 - inset),
        (-base_w / 2 + inset,  base_l / 2 - inset),
        ( base_w / 2 - inset, -base_l / 2 + inset),
        (-base_w / 2 + inset, -base_l / 2 + inset),
    ]
    result = (result.faces(">Z")
              .workplane(centerOption='CenterOfBoundBox')
              .pushPoints(corner_points)
              .hole(5))

    # === 3. Steg vereinigen ===
    steg = (cq.Workplane("XY")
            .box(steg_w, steg_l, steg_h)
            .translate((steg_x, 0, steg_z)))
    result = result.union(steg).clean()

    # === 4. Boss vereinigen ===
    boss = (cq.Workplane("XY")
            .cylinder(boss_h_val, boss_r)
            .translate((boss_x, 0, boss_z)))
    result = result.union(boss).clean()

    # === 5. Bohrung im Boss (nach Union!) ===
    boss_top_z = base_h + boss_h_val
    result = (result.faces(NearestToPointSelector((boss_x, 0, boss_top_z)))
              .workplane(centerOption='CenterOfBoundBox')
              .hole(8))

    # === 6. Querbohrung im Steg ===
    steg_right_face_x = steg_x + steg_w / 2  # = 50
    steg_center_z = steg_z                     # = 25
    result = (result.faces(NearestToPointSelector(
                  (steg_right_face_x, 0, steg_center_z)))
              .workplane(centerOption='CenterOfBoundBox')
              .hole(6))

    return result
```

## Systematik: Feature-Build-Order

```
1. Basis erstellen
2. Subtraktive Features auf Basis (Bohrungen, Taschen) — >Z ist noch eindeutig
3. Additive Features vereinigen (Stege, Bosses) — eines nach dem anderen
4. Subtraktive Features auf additiven Features — NearestToPointSelector
5. Fillets / Chamfers — IMMER am Ende
```

## Häufige Fehler
1. **Bohrungen nach Union**: >Z trifft nicht mehr die Basis → VOR Union bohren oder NearestToPointSelector
2. **Mehrere Unions ohne Zwischenprüfung**: Nach jeder Union Face-Situation prüfen
3. **Feature-Positionen nicht vorberechnet**: Koordinaten am Anfang berechnen, nicht inline
