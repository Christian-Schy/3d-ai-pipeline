# Coordinate Transform Chain — Globale ↔ lokale Koordinaten
Tags: koordinaten, transform, global, lokal, umrechnung, position_berechnung, translate

## Wann verwenden
- Position eines Features in globalen Koordinaten berechnen
- translate()-Werte aus relativen Angaben ableiten
- Punkt für NearestToPointSelector bestimmen

## Berechnungsregeln

```python
# REGEL: .box() zentriert in X/Y um den Workplane-Ursprung
# Z-Verhalten hängt von centered ab

# Box am Ursprung (Standard):
# box(100, 80, 20) → X: -50..+50, Y: -40..+40, Z: -10..+10
# box(100, 80, 20, centered=(True, True, False)) → X: -50..+50, Y: -40..+40, Z: 0..+20

# TRANSLATE verschiebt das ZENTRUM des Körpers
# box(20, 20, 10) + translate((30, 0, 25))
# → Zentrum bei (30, 0, 25)
# → X: 20..40, Y: -10..10, Z: 20..30

# POSITION EINES FEATURES BERECHNEN:
# base: box(100, 100, 20, centered=(T,T,F))
#   → Basis-Top bei Z=20
# steg: box(10, 50, 15).translate((40, 0, Z))
#   → Steg-Zentrum-Z = Basis-Top + Steg-Höhe/2 = 20 + 7.5 = 27.5
#   → translate((40, 0, 27.5))
#   → Steg: X: 35..45, Y: -25..25, Z: 20..35
#   → Steg-Top bei Z=35

# FÜR NearestToPointSelector:
# Steg-Top-Face: (40, 0, 35)
# Steg-Rechte-Face: (45, 0, 27.5)
# Steg-Vorder-Face: (40, -25, 27.5)


def calculate_translate_z(base_z: float, feature_height: float,
                           base_centered_z: bool = False) -> float:
    """Berechnet die Z-Translation für ein Feature auf einer Basis.

    Args:
        base_z: Höhe der Basis (mm)
        feature_height: Höhe des Features (mm)
        base_centered_z: Ob die Basis in Z zentriert ist
    """
    if base_centered_z:
        base_top = base_z / 2
    else:
        base_top = base_z
    return base_top + feature_height / 2


def calculate_feature_face_point(base_dims: tuple, base_centered: bool,
                                  feature_dims: tuple, feature_translate: tuple,
                                  face: str) -> tuple:
    """Berechnet den Punkt für NearestToPointSelector auf einer Feature-Face.

    Args:
        base_dims: (x, y, z) Basis-Abmessungen
        feature_dims: (x, y, z) Feature-Abmessungen
        feature_translate: (tx, ty, tz) Translation des Features
        face: ">Z", "<Z", ">X", "<X", ">Y", "<Y"
    """
    tx, ty, tz = feature_translate
    fx, fy, fz = feature_dims

    points = {
        ">Z": (tx, ty, tz + fz / 2),
        "<Z": (tx, ty, tz - fz / 2),
        ">X": (tx + fx / 2, ty, tz),
        "<X": (tx - fx / 2, ty, tz),
        ">Y": (tx, ty + fy / 2, tz),
        "<Y": (tx, ty - fy / 2, tz),
    }
    return points.get(face, (tx, ty, tz))
```

## Referenz-Tabelle: Position häufiger Platzierungen

Basis: box(W, L, H, centered=(True, True, False)) → X: -W/2..+W/2, Y: -L/2..+L/2, Z: 0..H

| Platzierung | translate X | translate Y | translate Z |
|-------------|-----------|-----------|-----------|
| Mittig oben | 0 | 0 | H + fz/2 |
| Rechts oben | W/2 - fx/2 | 0 | H + fz/2 |
| Links oben | -W/2 + fx/2 | 0 | H + fz/2 |
| Hinten oben | 0 | L/2 - fy/2 | H + fz/2 |
| Vorne oben | 0 | -L/2 + fy/2 | H + fz/2 |
| Rechts hinten oben | W/2 - fx/2 | L/2 - fy/2 | H + fz/2 |

(fx, fy, fz = Feature-Dimensionen)

## Häufige Fehler
1. **Z-Berechnung**: translate-Z für Feature = Basis-Top + Feature-Höhe/2 (Zentrum!)
2. **Bündig am Rand**: translate-X = Basis-Breite/2 - Feature-Breite/2 (nicht Basis-Breite/2)
3. **Zentrierte vs. nicht-zentrierte Basis**: Bei centered=(T,T,F) beginnt Z bei 0. Bei centered=(T,T,T) beginnt Z bei -H/2
