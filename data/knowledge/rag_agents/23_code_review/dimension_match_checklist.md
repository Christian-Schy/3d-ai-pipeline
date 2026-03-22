# Dimension Match — Code-Maße = Blueprint-Maße?
Tags: dimension, vergleich, maße, blueprint, match

## Checkliste (Blueprint Feature Tree vs. Code vergleichen)

### Für jedes Feature prüfen:

1. ✓ Blueprint sagt x=100 → Code hat .box(100, ...) oder Konstante BASE_W=100?
2. ✓ Blueprint sagt diameter=10 → Code hat .hole(10) (NICHT .hole(5))?
3. ✓ Blueprint sagt depth=null → Code hat .hole(d) ohne depth?
4. ✓ Blueprint sagt depth=15 → Code hat .hole(d, 15)?
5. ✓ Blueprint sagt n_holes=6 → Code hat 6 Punkte in pushPoints oder n=6?
6. ✓ Blueprint sagt circle_diameter=60 → Code berechnet radius=30 korrekt?
7. ✓ Blueprint sagt position=flush_right → Code hat offset berechnet?

### Position prüfen:
8. ✓ translate_z im Code = basis_H + feature_H/2?
9. ✓ Flush-Offset im Code = parent_dim/2 - feature_dim/2?
10. ✓ NearestToPointSelector Punkt = korrekte Feature-Top-Koordinaten?

### Anzahl prüfen:
11. ✓ Anzahl Funktionen = Anzahl Features im Blueprint?
12. ✓ Jedes Blueprint-Feature hat eine Funktion im Code?

## Fehler-Meldungen
- "FEHLER: Blueprint sagt ∅10 aber Code hat .hole(5) — Radius statt Durchmesser?"
- "FEHLER: Blueprint hat 6 Löcher aber Code hat 4 pushPoints"
- "FEHLER: translate_z=20 aber sollte 25 sein (basis_H=20 + feat_H/2=5)"
