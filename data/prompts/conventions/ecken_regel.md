Ecken-Regel (Feature in einer Ecke der Face, mit Versatz):
  Steht das Feature "in der oberen rechten Ecke" o.ae. und ist von dort
  versetzt, besitzt es genau zwei abstand_-Keys — den der HORIZONTALEN
  und den der VERTIKALEN Eck-Kante. Die Bewegungsrichtung bestimmt die
  Zuordnung:
    "nach links" / "nach rechts"  = HORIZONTALE Bewegung
                                    -> Wert gehoert zur HORIZONTALEN Eck-Kante.
    "nach oben"  / "nach unten"   = VERTIKALE Bewegung
                                    -> Wert gehoert zur VERTIKALEN Eck-Kante.
  Pro Ecke:
    obere rechte Ecke:   "X nach links"  -> abstand_rechts: X
                         "Y nach unten"  -> abstand_oben:   Y
    obere linke Ecke:    "X nach rechts" -> abstand_links:  X
                         "Y nach unten"  -> abstand_oben:   Y
    untere rechte Ecke:  "X nach links"  -> abstand_rechts: X
                         "Y nach oben"   -> abstand_unten:  Y
    untere linke Ecke:   "X nach rechts" -> abstand_links:  X
                         "Y nach oben"   -> abstand_unten:  Y
  Die Reihenfolge der Werte im Text ist egal — nur die Bewegungsrichtung
  bestimmt die Zuordnung. WICHTIG: "nach links/rechts/oben/unten" ist in
  einer Ecken-Phrase NUR Bewegungsrichtung — niemals selbst ein
  versatz_-Key. Eine Ecke ergibt immer abstand_*, nie versatz_* / kante_*.
