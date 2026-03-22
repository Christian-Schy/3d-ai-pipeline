# Nut- und Schlitzregeln

## Nut/Slot-Typen
- Nut auf Fläche: type="slot", params={length, width, depth}
- Rechteckige Tasche: type="pocket_rect", params={x, y, depth}
- Ausschnitt: type="cutout", params={x, y, depth=null}

## Tiefe
- depth=null → Durchgangsschnitt (durch ganzes Material)
- depth=X → Blind-Nut, nur X mm tief (depth MUSS < parent.z sein!)
- "Nut bleibt auf der Oberfläche" → explizite Tiefe angeben

## Positionierung
- Nut zentriert: offset_x=0, offset_y=0
- Nut entlang X-Achse: length=große Dimension, width=kleine Dimension
- Nut entlang Y-Achse: length=große Dimension in Y, width in X

### ★ Full-length Nut (length=null = volle Parent-Dimension)
- Wenn length=null: Die Nut erstreckt sich über die GESAMTE Parent-Dimension in Nut-Richtung
- ★ offset in Nut-Richtung MUSS 0 sein! Ein Offset verschiebt das Rect-Zentrum und die Nut ragt über den Rand!
- Beispiel: Basis 30×30, "Nut entlang Y": length=null(=30), offset_y=0, offset_x=0
- ★ FALSCH: offset_y=-15 → .center(0,-15).rect(5,30) → Nut geht von Y=-30 bis Y=0 → halb außerhalb des Würfels!

## ★ Nut-Maßangabe "AxB" (z.B. "5x5", "10x3")
- "Nut 5x5" = Breite 5mm × Tiefe 5mm (width=5, depth=5)
- "Nut 10x3" = Breite 10mm × Tiefe 3mm (width=10, depth=3)
- Erstes Maß = Breite (Querschnitt), Zweites Maß = Tiefe (wie tief in Material)
- length wird SEPARAT angegeben oder ist null (= volle Parent-Dimension in Nut-Richtung)
- ★ NIEMALS depth = Parent-Höhe setzen, wenn User "5x5" sagt! depth=5, NICHT depth=30!

## Häufige Fehler
- depth=null wenn nur Oberflächennut gewünscht → immer explizite Tiefe!
- "5x5 Nut" als depth=Parent.z interpretiert → FALSCH! depth=5!
- length und width verwechseln → length ist die längere Dimension
- Nut größer als Parent → width/length prüfen gegen Parent-Maße
