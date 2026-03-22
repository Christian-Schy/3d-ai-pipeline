# Cut — Material entfernen (Boolean Subtraktion)
Tags: cut, schneiden, subtrahieren, entfernen, abziehen, ausschneiden, tasche, boolean_sub

## Wann verwenden
- Material aus einem Körper entfernen
- Tasche, Nut, Aussparung, Formschnitt
- Komplexe Formen die mit cutBlind/cutThruAll nicht möglich sind

## CadQuery Code (modulare Funktion)

```python
def cut_shape_from_body(body: cq.Workplane, tool: cq.Workplane) -> cq.Workplane:
    """Subtrahiert Tool-Form vom Body.

    Body - Tool = Ergebnis
    WICHTIG: Immer .clean() nach cut!
    """
    return body.cut(tool).clean()


def cut_slot(body: cq.Workplane, slot_width: float, slot_length: float,
             slot_depth: float, pos_x: float = 0, pos_y: float = 0,
             pos_z: float = 0) -> cq.Workplane:
    """Schneidet eine Nut/Slot via Boolean-Cut."""
    tool = (cq.Workplane("XY")
            .box(slot_width, slot_length, slot_depth)
            .translate((pos_x, pos_y, pos_z)))
    return body.cut(tool).clean()


def cut_cylinder_from_body(body: cq.Workplane, radius: float, height: float,
                            pos_x: float = 0, pos_y: float = 0,
                            pos_z: float = 0) -> cq.Workplane:
    """Schneidet einen Zylinder aus dem Body (runde Tasche/Bohrung)."""
    tool = (cq.Workplane("XY")
            .cylinder(height, radius)
            .translate((pos_x, pos_y, pos_z)))
    return body.cut(tool).clean()
```

## Parameter-Referenz
| Parameter | Typ | Beschreibung | Default |
|-----------|-----|--------------|---------|
| toCut | Workplane/Shape | Körper der abgezogen wird | — |
| clean | bool | Automatisch aufräumen | True |
| tol | float | Toleranz | None |

## Wann .cut() vs. .cutBlind() vs. .cutThruAll()
| Methode | Wann verwenden |
|---------|---------------|
| `.cutBlind(-d)` | Einfache Tasche, definierte Tiefe, auf einer Face |
| `.cutThruAll()` | Durchgangsschnitt, einfaches Profil |
| `.cut(tool)` | Komplexe 3D-Formen, schräge Schnitte, positionierte Tools |

## Häufige Fehler
1. **Tool überragt Body**: Wenn das Tool größer als der Body ist → dünne Restwände oder ungültiger Körper
2. **Tool berührt Body nicht**: Cut hat keinen Effekt, kein Fehler aber auch keine Änderung
3. **★ .clean() vergessen**: Interne Faces bleiben → STL-Probleme
4. **Tool-Position falsch**: `.translate()` Koordinaten sorgfältig berechnen — Zentrum des Tools beachten
