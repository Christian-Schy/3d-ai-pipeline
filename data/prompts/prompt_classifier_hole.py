# HOLE CLASSIFIER — one phrase -> coarse bohrung classification
#
# SYSTEM_PROMPT wird aus der Konventions-Bibliothek (ADR 0014 W2)
# zusammengesetzt: klassifizierer-spezifischer Kopf + geteilte Fragmente.

from src.utils.prompt_loader import load_convention

_SEITE = load_convention("seite")
_PUNKT = load_convention("punkt_positionierung")
_ECKEN = load_convention("ecken_regel")
_JSON_ONLY = load_convention("json_only")


SYSTEM_PROMPT = f"""Du klassifizierst genau EINE CAD-Aktions-Phrase fuer Bohrungen/Locher.

Antwort: striktes JSON mit den Feldern typ, seite, parameter_hints.

typ:
  Immer "bohrung".

{_SEITE}

parameter_hints:
  Nur explizite Zahlen aus der Phrase.
  Erlaubte Keys:
    durchmesser, tiefe
    abstand_oben, abstand_unten, abstand_rechts, abstand_links,
    abstand_vorne, abstand_hinten
    versatz_oben, versatz_unten, versatz_rechts, versatz_links,
    versatz_vorne, versatz_hinten

{_PUNKT}

{_ECKEN}

{_JSON_ONLY}"""


CLASSIFIER_TEMPLATE = """\
TEIL-TYP: {teil_type}
TEIL-MASSE: {teil_params}
PARENT-PHRASE: {parent_phrase}

PHRASE:
{phrase}

JSON:"""
