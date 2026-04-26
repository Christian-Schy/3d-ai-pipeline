# Offsets und Spezialfälle — Abstände, Kanten, Ecken
Tags: offset, abstand, kante, rand, ecke, versetzt, position, edge

## Offset-Berechnung

Offsets werden VOM BLUEPRINT ASSEMBLER berechnet, nicht vom Part Position Assigner!
Der PPA gibt nur Hinweise (alignment, distance_mm, gap_mm) weiter.

ABER: Wenn die Spec EXPLIZITE Offsets nennt, diese als offset_x/offset_y setzen.

## Explizite Offsets aus der Spezifikation

### "Xmm vom rechten Rand"
-> alignment="flush_right" ODER offset_x berechnen
Berechnung: offset_x = +(Parent_X/2 - Child_X/2 - Xmm)

### "Xmm vom linken Rand"
-> offset_x = -(Parent_X/2 - Child_X/2 - Xmm)

### "Xmm vom vorderen Rand"
-> offset_y = -(Parent_Y/2 - Child_Y/2 - Xmm)

### "Xmm vom hinteren Rand"
-> offset_y = +(Parent_Y/2 - Child_Y/2 - Xmm)

MERKE: Exakte Berechnung macht der Blueprint Assembler!
Der PPA muss nur die RICHTUNG (alignment) und den ABSTAND (gap_mm) weitergeben.

## Ecken-Positionierung

### "in der rechten hinteren Ecke"
-> face=">Z", alignment="flush_right", offset_y: positiv (hinten)
Oder einfacher: alignment="flush_right_top" (wenn unterstützt)

### "in der linken vorderen Ecke"
-> face=">Z", alignment="flush_left", offset_y: negativ (vorne)

## Spezialfälle

### Gleiches Teil, mehrere Positionen
"4 Stützen in den Ecken" — Feature Tagger macht daraus EIN Pattern.
Part Position Assigner behandelt es als centered (Muster-Logik im Coder).

### Teil ragt über den Parent hinaus
Wenn ein Teil breiter als der Parent ist: centered, der Überstand ist gewollt.
Keine Warnung, kein Fehler — manche Designs haben das absichtlich.

### Teil mit gleichen Dimensionen wie Parent
"Deckel gleich groß wie Basis" -> alignment="centered", alles bündig.

### Teil nur in einer Dimension kleiner
"Platte 100×50×10 auf Basis 100×100×20"
X gleich, Y kleiner -> centered oder alignment je nach Spec.
