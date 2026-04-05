# Face-Berechnung — Welche Face hat welche Maße?
Tags: face, seite, fläche, berechnung, dimension, bohrung, nut

## Grundregel: Face = Mathe, kein Raten!

Eine Box mit params x/y/z hat diese Faces:
- **>X Face** (rechte Seite): Maße = **Y × Z**
- **<X Face** (linke Seite): Maße = **Y × Z**
- **>Y Face** (hintere Seite): Maße = **X × Z**
- **<Y Face** (vordere Seite): Maße = **X × Z**
- **>Z Face** (Oberseite): Maße = **X × Y**
- **<Z Face** (Unterseite): Maße = **X × Y**

## Schritt-für-Schritt: "von der AxB Seite"

1. Lies die Maße aus der Beschreibung: "80×40 Seite"
2. Schau dir die Parent-Box an: x=20, y=80, z=40
3. Berechne JEDE Face:
   - >X = Y×Z = 80×40 ✓ TREFFER!
   - >Y = X×Z = 20×40 ✗
   - >Z = X×Y = 20×80 ✗
4. Ergebnis: face=">X"

## Beispiel: Platte 20×80×40, Bohrung auf 80×40 Seite

Parent plate_right: x=20, y=80, z=40
"80×40 Seite" → sortiert [40, 80]

| Face | Dimensionen | Sortiert | Match? |
|------|------------|----------|--------|
| >X   | Y×Z = 80×40 | [40, 80] | ✓ JA |
| >Y   | X×Z = 20×40 | [20, 40] | ✗ |
| >Z   | X×Y = 20×80 | [20, 80] | ✗ |

→ face=">X", face_hint="von der 80×40 Seite"

## Beispiel: Würfel 30×30×30, Bohrung von oben

"von oben" → face=">Z" (keine Berechnung nötig, direkte Angabe)

## Beispiel: Platte 100×50×10, Bohrung durch die Dicke

"durch die Dicke" → dünnste Dimension = z=10
→ Bohrung geht durch die dünnste Seite = face=">Z"

## MERKE: face_hint IMMER setzen wenn Maße genannt werden

Wenn "AxB Seite/Fläche" in der Beschreibung steht:
→ face_hint = "von der AxB Seite" (wörtlich übernehmen)
Das System validiert die Face-Berechnung damit nochmal deterministisch.
