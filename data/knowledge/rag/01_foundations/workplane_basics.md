# Workplane Basics — Arbeitsebene erstellen und verstehen
Tags: workplane, arbeitsebene, XY, XZ, YZ, ebene, grundlage, basis

## Wann verwenden
- User erstellt ein neues Teil (immer mit Workplane starten)
- User wechselt die Arbeitsebene für Features auf anderen Flächen
- Jede CadQuery-Operation beginnt auf einer Workplane

## CadQuery Code (modulare Funktion)

```python
# Workplane auf Hauptebenen
wp_xy = cq.Workplane("XY")   # Draufsicht: X nach rechts, Y nach hinten
wp_xz = cq.Workplane("XZ")   # Vorderansicht: X nach rechts, Z nach oben
wp_yz = cq.Workplane("YZ")   # Seitenansicht: Y nach hinten, Z nach oben

# Workplane mit Versatz (offset)
wp_offset = cq.Workplane("XY").workplane(offset=20)  # 20mm über XY-Ebene

# Workplane auf existierender Face
def get_workplane_on_face(body: cq.Workplane, face_selector: str) -> cq.Workplane:
    """Erstellt Workplane auf einer Face des Körpers."""
    return body.faces(face_selector).workplane(centerOption='CenterOfBoundBox')

# Workplane mit verschobenem Ursprung
wp_moved = cq.Workplane("XY").center(10, 20)  # Ursprung auf (10, 20) verschieben
```

## Parameter-Referenz
| Parameter | Typ | Beschreibung | Default |
|-----------|-----|--------------|---------|
| plane | str | "XY", "XZ", "YZ", "front", "back", "top", "bottom", "left", "right" | "XY" |
| offset | float | Versatz senkrecht zur Ebene in mm | 0 |
| centerOption | str | "CenterOfMass", "CenterOfBoundBox", "ProjectedOrigin" | "ProjectedOrigin" |

## Varianten
- `cq.Workplane("front")` = gleich wie `"XZ"`
- `cq.Workplane("top")` = gleich wie `"XY"`
- `cq.Workplane("right")` = gleich wie `"YZ"`

## Häufige Fehler
1. **Falsche Ebene gewählt**: XY = Draufsicht (Z nach oben), XZ = Frontansicht → bei "Vorderansicht" XZ nehmen
2. **centerOption vergessen**: Nach `.faces().workplane()` ist der Ursprung NICHT immer in der Mitte → `centerOption='CenterOfBoundBox'` explizit setzen
3. **Offset-Richtung**: Offset geht in Normalenrichtung der Ebene — bei "XY" nach +Z
