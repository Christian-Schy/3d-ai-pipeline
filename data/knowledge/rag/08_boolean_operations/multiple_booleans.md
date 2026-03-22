# Multiple Booleans — Sequentielle Booleans richtig verketten
Tags: mehrere, sequenziell, kette, chain, multiple_booleans, reihenfolge

## Wann verwenden
- Mehr als eine Boolean-Operation hintereinander
- Komplexe Teile mit mehreren Aufsätzen und Schnitten
- Feature Tree mit 3+ Features

## CadQuery Code (modulare Funktion)

```python
def build_multi_feature(features_ordered: list) -> cq.Workplane:
    """Baut ein Teil Schritt für Schritt aus Features auf.

    Args:
        features_ordered: Liste von (operation, body) Tupeln
            operation: "base", "union", "cut"
            body: cq.Workplane Objekt
    """
    result = None
    for op, feature in features_ordered:
        if op == "base":
            result = feature
        elif op == "union":
            result = result.union(feature).clean()
        elif op == "cut":
            result = result.cut(feature).clean()
    return result


# Beispiel: Platte + 2 Stege + 3 Bohrungen
def example_complex_part():
    # 1. Basis
    base = cq.Workplane("XY").box(100, 100, 20, centered=(True, True, False))

    # 2. Steg links
    steg_l = cq.Workplane("XY").box(10, 80, 25).translate((-40, 0, 22.5))
    base = base.union(steg_l).clean()

    # 3. Steg rechts
    steg_r = cq.Workplane("XY").box(10, 80, 25).translate((40, 0, 22.5))
    base = base.union(steg_r).clean()

    # 4. Bohrung links (im Steg!)
    from cadquery.selectors import NearestToPointSelector
    base = (base.faces(NearestToPointSelector((-40, 0, 35)))
            .workplane(centerOption='CenterOfBoundBox')
            .hole(6))

    # 5. Bohrung rechts (im Steg!)
    base = (base.faces(NearestToPointSelector((40, 0, 35)))
            .workplane(centerOption='CenterOfBoundBox')
            .hole(6))

    # 6. Zentrale Bohrung (in Basis)
    base = (base.faces(NearestToPointSelector((0, 0, 20)))
            .workplane(centerOption='CenterOfBoundBox')
            .hole(12))

    return base
```

## Regeln für sequentielle Booleans
1. **Immer .clean() zwischen Booleans** — nie `a.union(b).union(c)` ohne clean
2. **Variable wiederverwenden**: `result = result.union(x).clean()` — nicht neue Variablen
3. **NearestToPointSelector nach jeder Union**: Face-Selektoren werden nach jeder Union unzuverlässiger
4. **Bohrungen in der richtigen Reihenfolge**: Erst Features aufbauen, dann bohren

## Häufige Fehler
1. **Kein .clean() zwischen Booleans**: `body.union(a).union(b)` → intern kaputte Topologie
2. **Face-Selektor aus Schritt 1 in Schritt 5 verwenden**: Nach mehreren Booleans ist `>Z` nicht mehr vorhersagbar
3. **Alle Booleans auf einmal**: Besser Schritt für Schritt mit Zwischentests
