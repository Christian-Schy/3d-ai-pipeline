# Feature on Base — Feature direkt auf Grundkörper platzieren
Tags: feature_auf_basis, aufsatz, platzieren, basis, grundkörper, aufsetzen, additive_feature, feature_add, boss, extrude_on_base, add_boss, add_block, block_on_plate

## Wann verwenden
- Erstes Feature (Steg, Boss, Tasche) auf dem Grundkörper
- Noch keine Union erfolgt → einfache Face-Selektion möglich

## CadQuery Code (modulare Funktion)

```python
def add_rect_extrusion_on_base(base: cq.Workplane,
                                width: float, length: float, height: float,
                                face: str = ">Z",
                                offset_x: float = 0,
                                offset_y: float = 0) -> cq.Workplane:
    """Extrudiert ein Rechteck auf einer Basisfläche.

    Für das ERSTE Feature auf der Basis ist >Z sicher.
    """
    return (base.faces(face)
            .workplane(centerOption='CenterOfBoundBox')
            .center(offset_x, offset_y)
            .rect(width, length)
            .extrude(height))


def add_circular_boss_on_base(base: cq.Workplane,
                               radius: float, height: float,
                               face: str = ">Z",
                               offset_x: float = 0,
                               offset_y: float = 0) -> cq.Workplane:
    """Zylindrischer Boss auf der Basis."""
    return (base.faces(face)
            .workplane(centerOption='CenterOfBoundBox')
            .center(offset_x, offset_y)
            .circle(radius)
            .extrude(height))


# Vollständiges Beispiel
def example_plate_with_boss():
    # Basis: 100x100x10 Platte
    base = cq.Workplane("XY").box(100, 100, 10, centered=(True, True, False))

    # Boss: ∅30, 15mm hoch, 20mm nach rechts versetzt
    result = add_circular_boss_on_base(base, radius=15, height=15,
                                        offset_x=20, offset_y=0)
    return result
```

## Positionierung auf der Basis
| User sagt | offset_x | offset_y | Face |
|-----------|----------|----------|------|
| "mittig" | 0 | 0 | >Z |
| "rechts" | +breite/2 - feat/2 | 0 | >Z |
| "links" | -breite/2 + feat/2 | 0 | >Z |
| "vorne" | 0 | -länge/2 + feat/2 | >Z |
| "hinten" | 0 | +länge/2 - feat/2 | >Z |
| "oben rechts hinten" | +x_off | +y_off | >Z |
| "auf der Seite" | 0 | 0 | >X / <X |

## Häufige Fehler
1. **Flush-Positionierung**: "bündig rechts" = offset_x = basis_breite/2 - feature_breite/2
2. **"oben" vs ">Z"**: "oben" bei einer Platte = >Z Face. Aber "oben auf der rechten Seite" = >Z + offset_x
3. **Extrude combine**: `.extrude(h)` mit combine=True (default) fügt automatisch zur Basis hinzu — kein separater union nötig
