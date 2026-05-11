# EDGE FEATURE CLASSIFIER — one phrase -> fase or rundung

SYSTEM_PROMPT = """Du klassifizierst genau EINE CAD-Aktions-Phrase fuer Kantenfeatures:
Fasen und Rundungen.

Antwort: striktes JSON mit den Feldern typ, seite, parameter_hints.

typ:
  fase | rundung

seite:
  oben | unten | rechts | links | vorne | hinten
  Wenn die Phrase keine eigene Seite nennt, erbe die Seite aus PARENT-PHRASE.

parameter_hints:
  Nur explizite Zahlen aus der Phrase.
  Erlaubte Keys:
    groesse, radius, kantenlaenge

Regeln:
  "fase 2mm" -> typ "fase", groesse: 2.
  "radius 3mm", "abrunden", "rundung" -> typ "rundung", radius: 3.
  Keine Bohrungs-, Taschen- oder Nut-Parameter ausgeben.

Antworte NUR mit dem JSON-Objekt. Kein Markdown, keine Erklaerung."""


CLASSIFIER_TEMPLATE = """\
TEIL-TYP: {teil_type}
TEIL-MASSE: {teil_params}
PARENT-PHRASE: {parent_phrase}

PHRASE:
{phrase}

JSON:"""
