# Intersect — Schnittmenge zweier Körper
Tags: intersect, schnittmenge, gemeinsam, overlap, überlappung

## Wann verwenden
- Nur den Bereich behalten wo sich zwei Körper überlappen
- Formen beschneiden (z.B. Kugel + Box = abgerundeter Block)
- Selten, aber nützlich für organische Formen

## CadQuery Code (modulare Funktion)

```python
def intersect_bodies(body_a: cq.Workplane, body_b: cq.Workplane) -> cq.Workplane:
    """Behält nur die Schnittmenge beider Körper."""
    return body_a.intersect(body_b).clean()


# Beispiel: Abgerundeter Block
def rounded_block(width: float, height: float, sphere_radius: float) -> cq.Workplane:
    """Block mit sphärisch abgerundeten Ecken."""
    box = cq.Workplane("XY").box(width, width, height)
    sphere = cq.Workplane("XY").sphere(sphere_radius)
    return box.intersect(sphere).clean()
```

## Häufige Fehler
1. **Keine Überlappung**: Wenn Körper sich nicht berühren → leerer Körper (Error)
2. **Reihenfolge egal**: `a.intersect(b)` = `b.intersect(a)` (kommutativ)
3. **Selten gebraucht**: Meistens ist `.cut()` das was man eigentlich will
