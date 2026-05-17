# POCKET CLASSIFIER — one phrase -> tasche classification
#
# SYSTEM_PROMPT wird aus der Konventions-Bibliothek (ADR 0014 W2)
# zusammengesetzt: klassifizierer-spezifischer Kopf + geteilte Fragmente
# aus data/prompts/conventions/. Eine Konvention aendern = eine Datei dort.

from src.utils.prompt_loader import load_convention

_SEITE = load_convention("seite")
_FLAECHE = load_convention("flaeche_positionierung")
_ECKEN = load_convention("ecken_regel")
_ROTATION = load_convention("rotation")
_JSON_ONLY = load_convention("json_only")


SYSTEM_PROMPT = f"""Du klassifizierst genau EINE CAD-Aktions-Phrase fuer rechteckige Taschen/Ausnehmungen.

Antwort: striktes JSON mit den Feldern typ, seite, parameter_hints.

typ:
  Immer "tasche".

{_SEITE}

parameter_hints:
  Nur explizite Zahlen aus der Phrase.
  Erlaubte Keys:
    laenge, breite, hoehe, tiefe, rotation_deg
    abstand_oben, abstand_unten, abstand_rechts, abstand_links,
    abstand_vorne, abstand_hinten
    kante_oben, kante_unten, kante_rechts, kante_links,
    kante_vorne, kante_hinten
    versatz_oben, versatz_unten, versatz_rechts, versatz_links,
    versatz_vorne, versatz_hinten

{_FLAECHE}

{_ECKEN}

Hoehe/Tiefe:
  Wenn der Text bei einer Tasche "Hoehe" sagt, darfst du hoehe verwenden.
  Der deterministische Normalizer behandelt hoehe spaeter als Taschentiefe.

{_ROTATION}

{_JSON_ONLY}"""


CLASSIFIER_TEMPLATE = """\
TEIL-TYP: {teil_type}
TEIL-MASSE: {teil_params}
PARENT-PHRASE: {parent_phrase}

PHRASE:
{phrase}

JSON:"""
