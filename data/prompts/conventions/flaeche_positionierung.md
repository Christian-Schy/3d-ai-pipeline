Positionierung — Feature mit Aussenkanten (abstand_* vs kante_*):
  Pro Richtung EINZELN entscheiden:
    abstand_<richtung> = Abstand der Feature-MITTE zur Bauteilkante (DEFAULT).
    kante_<richtung>   = Abstand einer Feature-AUSSENKANTE zur Bauteilkante.

  STRIKTE Regel — kante_* NUR wenn der Text die Kante DES FEATURES
  ausdruecklich nennt ("Taschen-Kante", "Nut-Kante", "Kante der Tasche",
  "Kante des Features") ODER eine buendig-Phrase enthaelt ("buendig
  anliegend", "liegt auf der <X> Kante an"). Alles andere — auch "von
  linker Kante", "vom oberen Rand", "von der vorderen Kante 25mm" — ist
  abstand_*. Das Wort "Kante" allein reicht NICHT fuer kante_*.

  Beispiele (streng nach Wortlaut):
    "von linker Kante 18mm"                  -> abstand_links: 18
    "20mm von der rechten Kante"             -> abstand_rechts: 20
    "die obere Taschen-Kante 10mm vom Rand"  -> kante_oben: 10
    "obere Nut-Kante 15mm vom oberen Rand"   -> kante_oben: 15
    "oben buendig anliegend"                 -> kante_oben: 0

  Jede Richtung getrennt: eine kann kante_*, die andere abstand_* sein.
  Nie beide Keys fuer dieselbe Richtung.

  Verschiebung aus der Flaechen-Mitte:
    "10mm aus der Mitte nach hinten" -> versatz_hinten: 10.
  Zentriert / keine Positionsangabe -> gar keine Positionierungs-Keys.
