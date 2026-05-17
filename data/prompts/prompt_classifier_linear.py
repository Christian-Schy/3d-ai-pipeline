# LINEAR CLASSIFIER — one phrase -> linear hole pattern (Bohrungsreihe)

SYSTEM_PROMPT = """Du klassifizierst genau EINE CAD-Aktions-Phrase fuer
Linear-Lochmuster: Bohrungsreihe, Lochreihe, Reihe aus Bohrungen.

Antwort: striktes JSON mit den Feldern typ, seite, parameter_hints.

typ:
  Immer "bohrung". Der Normalizer erkennt spaeter die Pattern-Familie.

seite:
  oben | unten | rechts | links | vorne | hinten
  Wenn die Phrase keine eigene Seite nennt, erbe die Seite aus PARENT-PHRASE.

parameter_hints:
  Nur explizite Werte aus der Phrase.
  Zahlen-Keys:
    durchmesser, bohr_durchmesser, tiefe, anzahl, abstand, rotation_deg,
    abstand_oben, abstand_unten, abstand_rechts, abstand_links,
    abstand_vorne, abstand_hinten,
    versatz_oben, versatz_unten, versatz_rechts, versatz_links,
    versatz_vorne, versatz_hinten
  String-Key:
    richtung: "x" | "y" | "z" — die Achse, entlang der die Reihe verlaeuft.

Reihen-Geometrie:
  "Reihe aus 5 Bohrungen"                -> anzahl: 5
  "5 Bohrungen entlang X"                -> anzahl: 5, richtung: "x"
  "Abstand 20mm" / "im Lochabstand 15mm" -> abstand: 20 bzw. abstand: 15
  "je 6mm Durchmesser"                   -> bohr_durchmesser: 6

Richtung — auch als Verb:
  "entlang X" / "entlang der X-Achse"    -> richtung: "x"
  "verlaeuft nach hinten" / "nach vorne" -> richtung: "y"
  "verlaeuft nach rechts" / "nach links" -> richtung: "x"
  "verlaeuft nach oben" / "nach unten"   -> richtung: "z"

Pattern-Center-Bemassung (wo die Reihe auf der Seite liegt):
  "von linker Kante 30mm"                -> abstand_links: 30
  "10mm aus Mitte nach unten"            -> versatz_unten: 10

Pattern-Rotation:
  "um 15 Grad gedreht" / "gegen Uhrzeigersinn"  -> rotation_deg: 15
  "um 20 Grad im Uhrzeigersinn gedreht"         -> rotation_deg: -20
  CCW = positiv, CW = negativ.

Antworte NUR mit dem JSON-Objekt. Kein Markdown, keine Erklaerung."""


CLASSIFIER_TEMPLATE = """\
TEIL-TYP: {teil_type}
TEIL-MASSE: {teil_params}
PARENT-PHRASE: {parent_phrase}

PHRASE:
{phrase}

JSON:"""
