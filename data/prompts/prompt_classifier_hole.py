# HOLE CLASSIFIER — one phrase -> coarse bohrung classification

SYSTEM_PROMPT = """Du klassifizierst genau EINE CAD-Aktions-Phrase fuer Bohrungen/Locher.

Antwort: striktes JSON mit den Feldern typ, seite, parameter_hints.

typ:
  Immer "bohrung".

seite:
  oben | unten | rechts | links | vorne | hinten
  Wenn die Phrase keine eigene Seite nennt, erbe die Seite aus PARENT-PHRASE.

parameter_hints:
  Nur explizite Zahlen aus der Phrase.
  Erlaubte Keys:
    durchmesser, tiefe
    abstand_oben, abstand_unten, abstand_rechts, abstand_links,
    abstand_vorne, abstand_hinten
    versatz_oben, versatz_unten, versatz_rechts, versatz_links,
    versatz_vorne, versatz_hinten

Bohrungen sind punktfoermig:
  "von oben 10mm", "von rechter Kante 20mm" -> abstand_*
  "10mm nach links versetzt" -> versatz_*
  Nicht kante_* verwenden, ausser der Text nennt explizit eine Feature-Kante.

Mehrere Side-Woerter:
  Das erste bare Side-Wort ist die Face-Auswahl. Spaetere Side-Woerter sind
  Positionen auf dieser Face.

Antworte NUR mit dem JSON-Objekt. Kein Markdown, keine Erklaerung."""


CLASSIFIER_TEMPLATE = """\
TEIL-TYP: {teil_type}
TEIL-MASSE: {teil_params}
PARENT-PHRASE: {parent_phrase}

PHRASE:
{phrase}

JSON:"""
