# Relative Directions — "oben rechts hinten" → Koordinaten
Tags: richtung, direction, oben, unten, rechts, links, vorne, hinten, position_mapping

## Wann verwenden
- User beschreibt Position mit Richtungsangaben
- Interpreter muss Richtungen in Koordinaten/Faces umwandeln

## Koordinatensystem-Konvention

```
CadQuery Standard (Draufsicht = XY-Ebene):

         +Y (hinten)
          ↑
          |
  -X ←── ○ ──→ +X (rechts)
          |
          ↓
         -Y (vorne)

  +Z = oben (aus dem Bildschirm heraus)
  -Z = unten (in den Bildschirm hinein)
```

## Richtungs-Mapping

| User sagt | Achse | Vorzeichen | Face-Selektor |
|-----------|-------|-----------|---------------|
| oben | Z | + | >Z |
| unten | Z | - | <Z |
| rechts | X | + | >X |
| links | X | - | <X |
| hinten | Y | + | >Y |
| vorne | Y | - | <Y |

## Kombinierte Richtungen → Position

Basis: box(W, L, H, centered=(True, True, False))

| User sagt | offset_x | offset_y | face |
|-----------|----------|----------|------|
| "oben mittig" | 0 | 0 | >Z |
| "oben rechts" | +W/2 - feat/2 | 0 | >Z |
| "oben links" | -W/2 + feat/2 | 0 | >Z |
| "oben hinten" | 0 | +L/2 - feat/2 | >Z |
| "oben vorne" | 0 | -L/2 + feat/2 | >Z |
| "oben rechts hinten" | +W/2 - feat/2 | +L/2 - feat/2 | >Z |
| "oben links vorne" | -W/2 + feat/2 | -L/2 + feat/2 | >Z |
| "rechts mittig" | — | 0 (Y), 0 (Z) | >X |
| "rechts oben" | — | offset_z: +H/2 | >X |

## Berechnung "bündig am Rand"

```python
# Feature bündig am rechten Rand einer 100mm breiten Basis:
# Basis: X von -50 bis +50
# Feature: 20mm breit
# Bündig rechts: Feature-Rechte-Kante = Basis-Rechte-Kante
# → Feature-Zentrum X = 50 - 20/2 = 40
offset_x = basis_w / 2 - feature_w / 2

# Feature bündig am hinteren Rand:
offset_y = basis_l / 2 - feature_l / 2
```

## Kantenabstand — "Xmm von Kante entfernt"

Wenn ein Feature "X mm von einer Kante entfernt" platziert werden soll, wird das Feature-ZENTRUM berechnet:

**Formel (auf +Z-Fläche, Basis centered):**
```python
# Basis: box(W, L, H, centered=(True, True, False))
# Y geht von -L/2 bis +L/2, X geht von -W/2 bis +W/2

# "10mm von Unterkante (-Y)"
offset_y = -(L/2 - 10)     # NICHT -10!

# "10mm von Oberkante (+Y)"
offset_y = +(L/2 - 10)

# "10mm von rechter Kante (+X)"
offset_x = +(W/2 - 10)

# "10mm von linker Kante (-X)"
offset_x = -(W/2 - 10)
```

### Durchgerechnetes Beispiel
Würfel 30×30×30mm, Bohrung ∅10mm, "10mm von Unterkante":
- Unterkante = -Y Kante bei Y = -15
- Bohrungszentrum soll 10mm davon entfernt sein → Y = -15 + 10 = -5
- offset_y = -(30/2 - 10) = -(15 - 10) = **-5.0** ✓
- FALSCH wäre offset_y = -10.0 → Zentrum bei Y=-10, nur 5mm von Kante, Bohrungsrand (r=5) berührt Würfelkante!

## Seitenbohrungen — "parallel zur X/Y-Achse" / "durch die Seite"

Die Bohrungsachse bestimmt, auf welcher Fläche gebohrt wird:

| User sagt | Bohrung zeigt in | Face für Workplane |
|-----------|------------------|--------------------|
| "parallel zur X-Achse" / "in X-Richtung" | X | >Y oder <Y |
| "parallel zur Y-Achse" / "in Y-Richtung" | Y | >X oder <X |
| "parallel zur Z-Achse" / "von oben" | Z | >Z (Standard) |
| "von der Seite" / "seitlich" | Aus Kontext | >X, <X, >Y, <Y |
| "durch die Dicke" | Dünnste Dim | Face der dünnsten Dimension |

### Beispiel: Seitenbohrung durch Platte
Platte 10×50×50mm (X=10=Dicke, Y=50, Z=50), "Bohrung parallel zur X-Achse, 25mm von Oberkante":
- Bohrung zeigt in X → Workplane auf >Y oder <Y Fläche
- Auf der Y-Fläche: Koordinaten sind (X, Z)
- "25mm von Oberkante" → Oberkante = +Z → offset_z = +(50/2 - 25) = 0 (Mitte)
- → Fläche=>Y, Offset=(0, 0), depth=null (Durchgangsbohrung durch 10mm Dicke)

### Offset-Achsen auf Seitenflächen
Auf >X / <X Fläche: Workplane-Achsen sind (Y, Z)
Auf >Y / <Y Fläche: Workplane-Achsen sind (X, Z)
"von Oberkante Xmm" auf Seitenfläche → offset_z = +(H/2 - X)
"von Unterkante Xmm" auf Seitenfläche → offset_z = -(H/2 - X)

## Häufige Fehler
1. **Kantenabstand ≠ Offset**: "10mm von Kante" heißt NICHT offset=-10! Die Formel ist offset=-(Parent/2 - Abstand)
2. **Y-Achse invertiert**: In vielen CAD-Programmen ist Y=oben, in CadQuery ist Z=oben, Y=hinten!
2. **"rechts" bei Seitenansicht**: Wenn User die Seitenansicht meint, ist "rechts" = +Y, nicht +X
3. **"vorne" = -Y**: Kleineres Y = vorne (näher zum Betrachter). Kontraintuitiv!
4. **"oben rechts" auf Seitenfläche**: Auf >X Face ist "oben" = +Z und "rechts" = +Y (nicht +X!)
