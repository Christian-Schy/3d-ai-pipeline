# Nested Booleans — Verschachtelte Union + Cut Reihenfolge
Tags: verschachtelt, nested, union_und_cut, gemischt, reihenfolge, mixed_booleans

## Wann verwenden
- Sowohl Union (Stege, Bosses) als auch Cut (Bohrungen, Taschen) nötig
- Reihenfolge der Operationen beeinflusst das Ergebnis

## CadQuery Code — Richtige Reihenfolge

```python
from cadquery.selectors import NearestToPointSelector

def build_with_mixed_booleans():
    """
    RICHTIGE Reihenfolge für gemischte Booleans:

    Phase 1: Basis + subtraktive Features auf Basis
    Phase 2: Additive Features (Union) + .clean()
    Phase 3: Subtraktive Features auf additiven Features
    Phase 4: Fillets/Chamfers
    """

    # Phase 1: Basis mit Taschen/Bohrungen
    base = cq.Workplane("XY").box(100, 100, 20, centered=(True, True, False))
    base = (base.faces(">Z")
            .workplane(centerOption='CenterOfBoundBox')
            .rect(40, 40).cutBlind(-10))  # Tasche in Basis

    # Phase 2: Stege aufsetzen
    steg = cq.Workplane("XY").box(10, 60, 25).translate((40, 0, 22.5))
    body = base.union(steg).clean()

    # Phase 3: Bohrungen in Steg
    body = (body.faces(NearestToPointSelector((40, 0, 35)))
            .workplane(centerOption='CenterOfBoundBox')
            .hole(6))

    # Phase 4: Fillets
    body = body.edges("|Z").fillet(2)

    return body
```

## Anti-Pattern (FALSCH)

```python
# FALSCH: Alles durcheinander
base = cq.Workplane("XY").box(100, 100, 20, centered=(True, True, False))
steg = cq.Workplane("XY").box(10, 60, 25).translate((40, 0, 22.5))
body = base.union(steg).clean()         # Union
body = body.fillet(2)                    # FALSCH: Fillet VOR Bohrungen
body = body.faces(">Z").hole(6)         # Bohrung NACH Fillet → kann Fillet zerstören
body = body.faces(">Z").rect(40,40).cutBlind(-10)  # Tasche NACH Union → >Z trifft Steg
```

## Häufige Fehler
1. **Cut nach Union ohne NearestToPointSelector**: >Z nach Union ist unvorhersagbar
2. **Fillet vor dem letzten Boolean**: Fillet-Kanten werden durch Union/Cut zerstört
3. **Union → Cut → Union**: Zweite Union kann die Cut-Geometrie verändern → Reihenfolge planen
