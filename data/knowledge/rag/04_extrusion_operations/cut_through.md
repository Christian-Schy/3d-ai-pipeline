# CutThruAll — Durchgangsschnitt
Tags: durchschnitt, cutThruAll, durchgehend, ausschnitt, fenster, schlitz, langloch

## Wann verwenden
- User sagt: "durchgehend", "Ausschnitt", "Fenster", "Schlitz"
- Material komplett durchschneiden (keine Tiefenangabe nötig)
- Profile die durch den ganzen Körper gehen

## CadQuery Code (modulare Funktion)

```python
def cut_rect_through(body: cq.Workplane, face_selector: str,
                      width: float, length: float,
                      offset_x: float = 0, offset_y: float = 0) -> cq.Workplane:
    """Schneidet ein Rechteck komplett durch den Körper."""
    return (body.faces(face_selector)
            .workplane(centerOption='CenterOfBoundBox')
            .center(offset_x, offset_y)
            .rect(width, length)
            .cutThruAll())


def cut_slot_through(body: cq.Workplane, face_selector: str,
                      slot_length: float, slot_width: float,
                      offset_x: float = 0, offset_y: float = 0) -> cq.Workplane:
    """Schneidet ein Langloch (Slot) komplett durch."""
    return (body.faces(face_selector)
            .workplane(centerOption='CenterOfBoundBox')
            .center(offset_x, offset_y)
            .slot2D(slot_length, slot_width)
            .cutThruAll())


def cut_profile_through(body: cq.Workplane, face_selector: str,
                         points: list) -> cq.Workplane:
    """Schneidet ein beliebiges Profil komplett durch.

    Args:
        points: Liste von (x, y) Punkten die das Profil definieren
    """
    wp = (body.faces(face_selector)
          .workplane(centerOption='CenterOfBoundBox'))
    wire = wp.polyline(points).close()
    return wire.cutThruAll()
```

## Parameter-Referenz
| Parameter | Typ | Beschreibung | Default |
|-----------|-----|--------------|---------|
| (keine) | — | cutThruAll braucht keine Parameter | — |

## Varianten
- `.cutThruAll()`: Schneidet in BEIDE Richtungen der Workplane-Normalen
- Für nur eine Richtung: `.cutBlind(-9999)` als Workaround (sehr große Tiefe)

## Häufige Fehler
1. **Schneidet in beide Richtungen**: cutThruAll schneidet in +N UND -N der Workplane-Normalen → bei gestapelten Körpern werden ALLE durchschnitten
2. **Sketch auf falscher Face**: Wenn das Profil auf der falschen Face sitzt, wird die Form in die falsche Richtung projiziert
3. **Offenes Profil**: Der Sketch MUSS geschlossen sein → `.close()` bei polyline nicht vergessen

## Komposition
- Fenster in Wand: `body.faces(">X").workplane(cOBB).rect(w,h).cutThruAll()`
- Schlitz von oben: `body.faces(">Z").workplane(cOBB).slot2D(l,w).cutThruAll()`
- Beliebiger Ausschnitt: `body.faces(">Z").workplane(cOBB).polyline([...]).close().cutThruAll()`
