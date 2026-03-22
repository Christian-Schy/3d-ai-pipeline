# Selector Debugging — Selektoren testen und debuggen
Tags: debug, testen, prüfen, faces_auflisten, problem, fehlerbehebung, selector_test

## Wann verwenden
- Ein Selektor trifft die falsche Face
- Unklar welche Faces ein Körper hat
- Feature landet am falschen Ort

## CadQuery Code

```python
def debug_faces(body: cq.Workplane) -> list:
    """Listet alle Faces mit Position und Fläche auf."""
    solid = body.val()
    faces_info = []
    for i, face in enumerate(solid.Faces()):
        bb = face.BoundingBox()
        center = face.Center()
        area = face.Area()
        normal = face.normalAt()
        faces_info.append({
            'index': i,
            'center': (round(center.x, 2), round(center.y, 2), round(center.z, 2)),
            'area': round(area, 2),
            'normal': (round(normal.x, 2), round(normal.y, 2), round(normal.z, 2)),
            'bb_min': (round(bb.xmin, 2), round(bb.ymin, 2), round(bb.zmin, 2)),
            'bb_max': (round(bb.xmax, 2), round(bb.ymax, 2), round(bb.zmax, 2)),
        })
    return faces_info


def debug_selector(body: cq.Workplane, selector: str) -> dict:
    """Zeigt welche Face(s) ein Selektor trifft."""
    try:
        selected = body.faces(selector)
        face = selected.val()
        center = face.Center()
        return {
            'selector': selector,
            'hit': True,
            'center': (round(center.x, 2), round(center.y, 2), round(center.z, 2)),
            'area': round(face.Area(), 2),
        }
    except Exception as e:
        return {'selector': selector, 'hit': False, 'error': str(e)}


def export_intermediate(body: cq.Workplane, path: str):
    """Exportiert Zwischenstand für visuelle Inspektion."""
    cq.exporters.export(body, path)
```

## Debug-Workflow
1. `debug_faces(body)` → alle Faces auflisten
2. Prüfen: Welche Face hat die erwartete Position/Fläche?
3. `debug_selector(body, ">Z")` → trifft der Selektor richtig?
4. Falls falsch: `NearestToPointSelector` mit dem richtigen Zentrum
5. `export_intermediate()` → STL exportieren und visuell prüfen

## Häufige Fehler
1. **Face nach .clean() verschwunden**: `.clean()` kann koplanare Faces zusammenführen
2. **Mehr Faces als erwartet**: Union kann Schnittlinien-Faces erzeugen
3. **Normale invertiert**: Nach Cut kann eine Face die Normale-Richtung ändern
