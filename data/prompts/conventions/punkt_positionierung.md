Positionierung — punktfoermiges Feature:
  Das Feature (bei Mustern der Pattern-Mittelpunkt) ist ein Punkt. Seine
  Lage auf der Face wird mit zwei Werten je Achse beschrieben:
    abstand_<richtung> = Abstand des Punktes zur Bauteilkante. DEFAULT.
      "von linker Kante 20mm", "20mm von oben", "von der vorderen Kante
      30mm entfernt" -> abstand_*.
    versatz_<richtung> = Verschiebung aus der Flaechen-MITTE.
      "10mm aus der Mitte nach hinten", "von der Mitte 15mm nach rechts
      versetzt" -> versatz_*.
  Kein kante_* verwenden — ein Punkt hat keine Aussenkante.
  Zentriert / keine Positionsangabe -> gar keine Positionierungs-Keys.
