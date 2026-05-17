Anker (ADR 0014 W5):
  Anker = EXPLIZITE Verbindung eines Feature-Punkts mit einem Punkt
  des Parent-Bauteils ueber das Wort "AUF".

  Setze anker_eltern NUR wenn die Phrase EINES dieser drei Muster
  enthaelt:
    1.  "<feature-punkt> AUF <parent-punkt> des/der <parent>"
        z.B. "rechte Kante der Tasche AUF rechte Kante der Platte"
        z.B. "obere rechte Ecke der Bohrung AUF obere rechte Ecke des Wuerfels"
    2.  "liegt AUF der <X>-Kante (an)"
        z.B. "liegt auf rechter Kante an" -> anker_eltern: right_edge
    3.  "AUF <parent-punkt> des Wuerfels/der Platte"
        z.B. "auf der rechten Kante des Wuerfels"

  IM ZWEIFEL — KEINE anker_*-Keys setzen. Nahezu alle Phrasen sind
  positionierung, kein Anker.

  ANTI-BEISPIELE (KEIN Anker — das ist Positionierung):
    "die obere Taschen-Kante 10mm vom oberen Rand"
      -> kante_oben: 10  (edge-to-edge Positionierung)
    "die linke Nut-Kante 12mm vom linken Rand"
      -> kante_links: 12
    "in der oberen rechten Ecke 22mm nach links versetzt"
      -> abstand_rechts: 22, abstand_oben: <Y>  (Ecken-Regel)
    "von linker Kante 20mm"
      -> abstand_links: 20
    "oben buendig anliegend"
      -> kante_oben: 0
  Diese Phrasen nennen Bauteil-Raender, KEINEN Parent-Punkt. NICHT als
  Anker behandeln.

  Erlaubte Werte fuer anker_kind / anker_eltern:
    Ecken:  top_left | top_right | bottom_left | bottom_right
    Kanten: top_edge | bottom_edge | left_edge | right_edge
    Center: center

  Versatz: wenn ein Anker UND Versatz-Werte vorliegen, beide ueber
  versatz_<richtung> emittieren — der deterministische Bau macht daraus
  anchor.offset.
    "liegt auf rechter Kante an, 10mm nach oben versetzt"
      -> anker_eltern: right_edge, versatz_oben: 10
         (anker_kind weglassen -> defaults to center)

  WICHTIG: wenn anker_eltern fehlt, werden anker_kind-Werte IGNORIERT.
  Setze anker_kind nur, wenn du auch anker_eltern setzt.
