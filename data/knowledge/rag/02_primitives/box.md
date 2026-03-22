# Box — Quader / Platte erstellen
Tags: box, quader, platte, block, rechteck, kasten, würfel, cube, plate

## Wann verwenden
- User sagt: "Platte", "Block", "Quader", "Würfel", "Kasten", "Gehäuse-Grundkörper"
- Basis für fast alle Modelle
- Jede Angabe von Länge × Breite × Höhe

## CadQuery Code (modulare Funktion)

```python
def make_box(x: float, y: float, z: float,
             centered: bool = True) -> cq.Workplane:
    """Erstellt einen Quader.

    Args:
        x: Länge in X-Richtung (mm)
        y: Breite in Y-Richtung (mm)
        z: Höhe in Z-Richtung (mm)
        centered: True = zentriert am Ursprung, False = Ecke am Ursprung

    Returns:
        Quader als Workplane-Objekt.
        Bei centered=True: Mittelpunkt bei (0, 0, z/2)
        ACHTUNG: .box() zentriert in X und Y, aber Z geht von 0 bis z!
    """
    return cq.Workplane("XY").box(x, y, z, centered=(centered, centered, False))


def make_box_at_position(x: float, y: float, z: float,
                         pos_x: float, pos_y: float, pos_z: float) -> cq.Workplane:
    """Erstellt einen Quader an einer bestimmten Position (Zentrum)."""
    return (cq.Workplane("XY")
            .box(x, y, z)
            .translate((pos_x, pos_y, pos_z)))
```

## Parameter-Referenz
| Parameter | Typ | Beschreibung | Default |
|-----------|-----|--------------|---------|
| length | float | Größe in X (mm) | — |
| width | float | Größe in Y (mm) | — |
| height | float | Größe in Z (mm) | — |
| centered | bool/tuple | Zentriert auf Workplane | (True, True, True) |
| combine | bool | Mit bestehendem Körper kombinieren | True |

## Varianten
- `centered=True` (default): Box zentriert um Workplane-Ursprung in ALLEN Achsen
- `centered=(True, True, False)`: Zentriert in X/Y, Z beginnt bei Workplane
- `centered=False`: Ecke am Workplane-Ursprung, Box geht in +X, +Y, +Z

## Häufige Fehler
1. **Z-Zentrierung**: `.box(100, 100, 20)` mit Default centered=True → Z geht von -10 bis +10! Für Basis-Platte IMMER `centered=(True, True, False)` → Z geht von 0 bis 20.
2. **Verwechslung X/Y/Z**: CadQuery: X = rechts/links, Y = vorne/hinten, Z = oben/unten
3. **★★★ Z-Stacking Bug — box().translate() in add_* Funktionen FALSCH!**
   ```python
   # ❌ FALSCH — centered=(T,T,F) + translate_z = BASE_Z + H/2 erzeugt eine LÜCKE:
   aufsatz = cq.Workplane("XY").box(20, 50, 40, centered=(True, True, False))
   result = base.union(aufsatz.translate((40, 25, 20 + 40/2)))
   # Aufsatz geht von Z=40 bis Z=80 statt Z=20 bis Z=60! — 20mm Lücke!

   # ✓ RICHTIG für add_* Funktionen — face-basierte Extrusion:
   result = (base.faces(">Z")
             .workplane(centerOption='CenterOfBoundBox')
             .center(40, 25)
             .rect(20, 50)
             .extrude(40))
   # Startet automatisch auf der Oberfläche, kein Lücken-Risiko!
   ```

## Komposition
- Box als Basis (`make_*`): `cq.Workplane("XY").box(x, y, z, centered=(True, True, False))` ✓
- Box auf Basis (`add_*`): `body.faces(">Z").workplane(cOBB).center(ox,oy).rect(W,L).extrude(H)` ✓
- **NIEMALS** in `add_*`: separaten Body + `.translate()` + `.union()` — erzeugt Z-Lücken!
