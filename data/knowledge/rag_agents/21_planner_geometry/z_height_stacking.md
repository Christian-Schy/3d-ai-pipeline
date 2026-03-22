# Z-Height Stacking — Z-Berechnung bei gestapelten Features
Tags: z_höhe, stacking, stapeln, berechnen, translate_z

## Grundregel
Basis: centered=(True, True, False) → Z beginnt bei 0, Top bei H

## Translate-Z Formel für Feature auf Basis
```
translate_z = basis_H + feature_H / 2
```
(Weil box() standardmäßig in Z zentriert → Zentrum muss auf richtige Höhe)

## Beispiel-Berechnung: 3 Stufen

Basis:    100×100×20  → Z: 0..20     → Top: 20
Stufe 1:  60×60×15    → translate_z = 20 + 15/2 = 27.5  → Z: 20..35   → Top: 35
Stufe 2:  30×30×10    → translate_z = 35 + 10/2 = 40     → Z: 35..45   → Top: 45

## NearestToPointSelector Z-Werte
- Basis-Top:    (0, 0, 20)
- Stufe1-Top:   (0, 0, 35)
- Stufe2-Top:   (0, 0, 45)
- Stufe1-Seite: (0, 0, 27.5)   ← Mitte der Stufe, nicht Top!

## Feature-Top berechnen
```
feature_top_z = translate_z + feature_H / 2
             = basis_H + feature_H / 2 + feature_H / 2
             = basis_H + feature_H
```

## Multi-Stack
```
feature_n_top = basis_H + Σ(feature_i_H für i=1..n)
feature_n_translate_z = feature_n_top - feature_n_H / 2
```

## Häufige Fehler
1. translate_z = basis_H (FALSCH) → muss basis_H + feature_H/2 sein
2. NearestToPoint Z = translate_z (FALSCH für Top) → muss translate_z + feature_H/2 sein
3. centered=(True,True,True) statt (True,True,False) → Z geht von -H/2 bis +H/2
