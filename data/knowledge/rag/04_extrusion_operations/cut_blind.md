# CutBlind — Tasche mit definierter Tiefe
Tags: tasche, pocket, cutBlind, ausschnitt, vertiefung, nut, einsenkung, fräsen

## Wann verwenden
- User sagt: "Tasche", "Vertiefung", "Nut", "Einsenkung", "fräsen"
- Material entfernen bis zu einer bestimmten Tiefe (NICHT durchgehend)
- Rechteckige oder runde Taschen

## CadQuery Code (modulare Funktion)

```python
def cut_rect_pocket(body: cq.Workplane, face_selector: str,
                     width: float, length: float, depth: float,
                     offset_x: float = 0, offset_y: float = 0) -> cq.Workplane:
    """Fräst eine rechteckige Tasche in eine Fläche.

    Args:
        depth: Tiefe der Tasche (mm) — positiver Wert, geht ins Material
    """
    return (body.faces(face_selector)
            .workplane(centerOption='CenterOfBoundBox')
            .center(offset_x, offset_y)
            .rect(width, length)
            .cutBlind(-depth))


def cut_circular_pocket(body: cq.Workplane, face_selector: str,
                         radius: float, depth: float,
                         offset_x: float = 0, offset_y: float = 0) -> cq.Workplane:
    """Fräst eine runde Tasche in eine Fläche."""
    return (body.faces(face_selector)
            .workplane(centerOption='CenterOfBoundBox')
            .center(offset_x, offset_y)
            .circle(radius)
            .cutBlind(-depth))
```

## Parameter-Referenz
| Parameter | Typ | Beschreibung | Default |
|-----------|-----|--------------|---------|
| depth | float | Tiefe in mm — NEGATIV für ins Material | — |
| clean | bool | Körper aufräumen nach Schnitt | True |

## Varianten
- `.cutBlind(-10)`: 10mm tief ins Material (negativer Wert = ins Material)
- `.cutBlind(10)`: 10mm in Normalenrichtung der Workplane (positiv = weg vom Material)

## Häufige Fehler
1. **Vorzeichen**: `.cutBlind(-depth)` mit negativem Vorzeichen schneidet INS Material. Ohne Minus schneidet es in die falsche Richtung!
2. **Tiefe > Materialstärke**: Wenn depth > Wandstärke → Loch statt Tasche. Vorher prüfen
3. **Face-Selektor nach Boolean**: Nach einer Union kann `>Z` eine andere Face treffen → NearestToPointSelector verwenden
4. **★★★ body.cut(wp.slot2D().cutBlind()) — FATAL!** Diese Verschachtelung erzeugt `body - (body - slot) = nur die Nut` statt dem Körper mit Nut:
   ```python
   # ❌ FALSCH — erzeugt nur die Nut-Geometrie statt den Körper mit Nut:
   wp = body.faces(">Z").workplane(centerOption='CenterOfBoundBox')
   return body.cut(wp.slot2D(L, W).cutBlind(-D))

   # ✓ RICHTIG — direkt ketten auf body:
   return (body.faces(">Z")
           .workplane(centerOption='CenterOfBoundBox')
           .slot2D(L, W)
           .cutBlind(-D))
   ```

## ★★★ Nut vs. Langloch — Welches verwenden?

| Feature-Typ | Querschnitt | CadQuery | Anwendung |
|-------------|-------------|----------|-----------|
| `pocket_rect` / `groove` | RECHTECKIG | `.rect(w, l).cutBlind(-d)` | Nutfräsung, Kanal, Vertiefung |
| `slot` | ABGERUNDET (Langloch) | `.slot2D(l, d).cutBlind(-d)` | Langloch für Schraube, ovale Nut |

**★ STANDARD: Feature-Typ `pocket_rect` oder `groove` → IMMER `.rect().cutBlind()`, NIEMALS `slot2D()`!**
**`slot2D()` nur für echte Langlöcher mit abgerundeten Enden (Schlitze).**

```python
# RECHTECKIGE NUT (pocket_rect / groove) — Standard-Nut:
def cut_groove(body: cq.Workplane) -> cq.Workplane:
    return (body.faces(">Z")
            .workplane(centerOption='CenterOfBoundBox')
            .center(offset_x, offset_y)
            .rect(NUT_WIDTH, NUT_LENGTH)   # width x length
            .cutBlind(-NUT_DEPTH))         # negativ = ins Material

# LANGLOCH (slot) — NUR für ovale Aussparungen:
def cut_slot(body: cq.Workplane) -> cq.Workplane:
    return (body.faces(">Z")
            .workplane(centerOption='CenterOfBoundBox')
            .slot2D(SLOT_LENGTH, SLOT_DIAMETER)  # NUR Positionsargs!
            .cutBlind(-SLOT_DEPTH))
```

## slot2D API (nur für echte Langlöcher)
```python
# slot2D(length, diameter, angle=0) — NUR Positionsargumente, KEINE kwargs!
.slot2D(30, 5)           # 30mm lang, 5mm Breite
.slot2D(30, 5, angle=90) # gedrehte Nut
```
**❌ FALSCH**: `.slot2D(30, 5, centered=True)` — kein `centered` kwarg!
**❌ FALSCH**: `.rect(5, length=30)` — kein `length` kwarg!

## Komposition
- Tasche in Oberseite: `body.faces(">Z").workplane(cOBB).rect(w,l).cutBlind(-d)`
- Tasche in Seitenfläche: `body.faces(">X").workplane(cOBB).rect(w,l).cutBlind(-d)`
- Rechteckige Nut: `.rect(5, 30).cutBlind(-5)` = 5mm breit, 30mm lang, 5mm tief
