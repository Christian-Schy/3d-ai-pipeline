# Koordinatensystem — Achsen, Vorzeichen, Richtungen
Tags: koordinaten, achsen, xyz, richtung, konvention

## CadQuery Koordinatensystem
- X-Achse: rechts (+) / links (-)
- Y-Achse: hinten (+) / vorne (-)
- Z-Achse: oben (+) / unten (-)
- Ursprung: (0, 0, 0) = Mittelpunkt der Basis in X/Y

## Basis-Zentrierung (Standard)
box(W, L, H, centered=(True, True, False)):
- X: von -W/2 bis +W/2
- Y: von -L/2 bis +L/2
- Z: von 0 bis H (NICHT zentriert in Z!)

## Richtungs-Mapping
| User sagt | Achse | Vorzeichen | Face |
|-----------|-------|-----------|------|
| oben | Z | + | >Z |
| unten | Z | - | <Z |
| rechts | X | + | >X |
| links | X | - | <X |
| hinten | Y | + | >Y |
| vorne | Y | - | <Y |

## Faces nach Achse
| Face-Selektor | Treffer | Workplane-X | Workplane-Y |
|---------------|---------|------------|------------|
| >Z | Oberseite | → globales X | → globales Y |
| <Z | Unterseite | → globales X | → globales Y |
| >X | Rechte Seite | → globales Y | → globales Z |
| <X | Linke Seite | → globales Y | → globales Z |
| >Y | Rückseite | → globales X | → globales Z |
| <Y | Vorderseite | → globales X | → globales Z |

WICHTIG: Auf Seitenflächen (>X, <X, >Y, <Y) sind die Workplane-Achsen ANDERS als auf Top/Bottom!
