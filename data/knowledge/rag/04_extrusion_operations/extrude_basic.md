# Extrude Basic — Einfache Extrusion
Tags: extrude, extrusion, extrudieren, aufbauen, hochziehen, aufsatz, steg, rippe

## Wann verwenden
- User sagt: "extrudieren", "aufbauen", "Steg", "Rippe", "Aufsatz"
- 2D-Profil wird in die Höhe gezogen
- Feature auf bestehender Fläche aufbauen

## CadQuery Code (modulare Funktion)

```python
def extrude_rect_on_face(body: cq.Workplane, face_selector: str,
                          width: float, length: float, height: float,
                          offset_x: float = 0, offset_y: float = 0) -> cq.Workplane:
    """Extrudiert ein Rechteck auf einer bestehenden Fläche.

    Args:
        body: Bestehender Körper
        face_selector: z.B. ">Z" für Oberseite
        width: Breite des Rechtecks (mm)
        length: Länge des Rechtecks (mm)
        height: Extrusionshöhe (mm)
        offset_x: Versatz in X auf der Face (mm)
        offset_y: Versatz in Y auf der Face (mm)
    """
    return (body.faces(face_selector)
            .workplane(centerOption='CenterOfBoundBox')
            .center(offset_x, offset_y)
            .rect(width, length)
            .extrude(height))


def extrude_circle_on_face(body: cq.Workplane, face_selector: str,
                            radius: float, height: float,
                            offset_x: float = 0, offset_y: float = 0) -> cq.Workplane:
    """Extrudiert einen Kreis auf einer bestehenden Fläche (Boss)."""
    return (body.faces(face_selector)
            .workplane(centerOption='CenterOfBoundBox')
            .center(offset_x, offset_y)
            .circle(radius)
            .extrude(height))


def extrude_profile_flush_edge(body: cq.Workplane, face_selector: str,
                                width: float, length: float, height: float,
                                edge: str = "+X") -> cq.Workplane:
    """Extrudiert ein Profil bündig an einer Kante der Face.

    Args:
        edge: "+X" = rechter Rand, "-X" = links, "+Y" = hinten, "-Y" = vorne
    """
    wp = (body.faces(face_selector)
          .workplane(centerOption='CenterOfBoundBox'))

    # Bounding-Box der Face ermitteln für Kantenpositionierung
    bb = body.val().BoundingBox()

    offsets = {
        "+X": ((bb.xmax - bb.xmin) / 2 - width / 2, 0),
        "-X": (-(bb.xmax - bb.xmin) / 2 + width / 2, 0),
        "+Y": (0, (bb.ymax - bb.ymin) / 2 - length / 2),
        "-Y": (0, -(bb.ymax - bb.ymin) / 2 + length / 2),
    }
    ox, oy = offsets.get(edge, (0, 0))

    return (wp.center(ox, oy)
            .rect(width, length)
            .extrude(height))
```

## Parameter-Referenz
| Parameter | Typ | Beschreibung | Default |
|-----------|-----|--------------|---------|
| distance | float | Extrusionshöhe in mm | — |
| combine | bool | Mit Basis kombinieren | True |
| both | bool | In beide Richtungen extrudieren | False |
| taper | float | Schrägungswinkel in Grad | 0 |

## Varianten
- `.extrude(20)`: 20mm nach oben (in Normalenrichtung der Face)
- `.extrude(20, both=True)`: 10mm nach oben + 10mm nach unten
- `.extrude(20, taper=5)`: Konische Extrusion mit 5° Schräge

## Häufige Fehler
1. **Richtung**: `.extrude()` geht in Normalenrichtung der Workplane. Auf der Unterseite `<Z` geht Extrusion nach UNTEN (-Z)
2. **centerOption vergessen**: Ohne `centerOption='CenterOfBoundBox'` ist das Rechteck nicht auf der Face zentriert
3. **combine=True (default)**: Bei `.extrude(h)` auf einer Face wird das Feature automatisch mit dem Body vereinigt — manchmal unerwünscht wenn man es separat braucht
4. **★★★ FALSCH — box().translate() statt rect().extrude()**: NIEMALS separates Box-Objekt erstellen und union'd!
   ```python
   # ❌ FALSCH — Box schwebt in der Luft wenn Z-Centering falsch:
   boss = cq.Workplane("XY").box(W, L, H).translate((0, 0, BASE_H + H/2))
   return body.union(boss).clean()

   # ✓ RICHTIG — direkt auf Face extrudieren, kein Z-Centering nötig:
   return body.faces(">Z").workplane(centerOption='CenterOfBoundBox').rect(W, L).extrude(H)
   ```

## Komposition
- Steg auf Platte: `body.faces(">Z").workplane(cOBB).rect(w,l).extrude(h)`
- Rippe auf Seite: `body.faces(">X").workplane(cOBB).rect(w,l).extrude(h)`
- Aufsatz bündig an Kante: siehe `extrude_profile_flush_edge()` oben
