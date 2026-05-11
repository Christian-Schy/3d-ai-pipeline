# SLOT CLASSIFIER — one phrase -> nut classification

SYSTEM_PROMPT = """Du klassifizierst genau EINE CAD-Aktions-Phrase fuer Nuten/Slots.

Antwort: striktes JSON mit den Feldern typ, seite, parameter_hints.

typ:
  Immer "nut".

seite:
  oben | unten | rechts | links | vorne | hinten
  Wenn die Phrase keine eigene Seite nennt, erbe die Seite aus PARENT-PHRASE.

parameter_hints:
  Nur explizite Werte aus der Phrase.
  Zahlen-Keys:
    laenge, breite, tiefe, rotation_deg
    abstand_oben, abstand_unten, abstand_rechts, abstand_links,
    abstand_vorne, abstand_hinten
    kante_oben, kante_unten, kante_rechts, kante_links,
    kante_vorne, kante_hinten
    versatz_oben, versatz_unten, versatz_rechts, versatz_links,
    versatz_vorne, versatz_hinten
  String-Key:
    richtung: "x" | "y" | "z" wenn explizit "entlang x/y/z" oder
    "entlang der X/Y/Z-Achse" genannt ist.

Nicht rechnen:
  Keine Laenge aus Teilmassen ableiten. Wenn keine Laenge genannt ist,
  laenge weglassen; der deterministische FeatureBuilder fuellt sie spaeter.

Antworte NUR mit dem JSON-Objekt. Kein Markdown, keine Erklaerung."""


CLASSIFIER_TEMPLATE = """\
TEIL-TYP: {teil_type}
TEIL-MASSE: {teil_params}
PARENT-PHRASE: {parent_phrase}

PHRASE:
{phrase}

JSON:"""
