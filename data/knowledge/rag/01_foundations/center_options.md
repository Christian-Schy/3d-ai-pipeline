# Center Options — Workplane-Ursprung korrekt setzen
Tags: center, centerOption, CenterOfBoundBox, CenterOfMass, ProjectedOrigin, ursprung, mitte

## Wann verwenden
- Nach `.faces().workplane()` wenn Features zentriert platziert werden sollen
- Wenn Bohrungen oder Muster auf einer Fläche zentriert sein müssen
- Bei asymmetrischen Körpern wo CenterOfMass ≠ geometrische Mitte

## CadQuery Code (modulare Funktion)

```python
def workplane_centered_on_face(body: cq.Workplane, face_selector: str,
                                center: str = 'CenterOfBoundBox') -> cq.Workplane:
    """Workplane auf Face mit definiertem Zentrum.

    Args:
        center: 'CenterOfBoundBox' → geometrische Mitte der Face-BoundingBox
                'CenterOfMass' → Schwerpunkt der Face (bei Symmetrie = Mitte)
                'ProjectedOrigin' → globaler Ursprung projiziert auf Face
    """
    return body.faces(face_selector).workplane(centerOption=center)

# Beispiel: Bohrung in der Mitte der Oberseite
def drill_centered_hole(body: cq.Workplane, diameter: float) -> cq.Workplane:
    """Bohrung exakt in der Mitte der obersten Fläche."""
    return (body.faces(">Z")
            .workplane(centerOption='CenterOfBoundBox')
            .hole(diameter))
```

## Parameter-Referenz
| centerOption | Verhalten | Wann verwenden |
|-------------|-----------|----------------|
| `ProjectedOrigin` | Globaler Ursprung (0,0) auf die Face projiziert | Default; gut wenn Körper am Ursprung zentriert |
| `CenterOfBoundBox` | Mitte der Bounding-Box der Face | ★ Empfohlen für Features auf Faces — funktioniert immer |
| `CenterOfMass` | Flächenschwerpunkt | Nur bei symmetrischen Faces gleich wie BoundBox |

## Varianten
- Nach `.faces(">Z")` auf einem am Ursprung zentrierten 100x100 Körper:
  - `ProjectedOrigin` → (0, 0) — zufällig gleich wie Mitte
  - `CenterOfBoundBox` → (0, 0) — immer geometrische Mitte
- Nach `.faces(">Z")` auf einem Körper der bei (50, 50) sitzt:
  - `ProjectedOrigin` → (0, 0) relativ zu Face = Ecke!
  - `CenterOfBoundBox` → (50, 50) = korrekte Mitte

## Häufige Fehler
1. **ProjectedOrigin bei verschobenem Körper**: Wenn der Körper nicht am Ursprung zentriert ist, liegt ProjectedOrigin NICHT in der Mitte → immer `CenterOfBoundBox` verwenden
2. **CenterOfMass bei L-förmiger Face**: Schwerpunkt liegt nicht in der geometrischen Mitte → `CenterOfBoundBox` ist sicherer
3. **centerOption vergessen**: Default ist `ProjectedOrigin` — bei Face-basierter Arbeit fast immer falsch
