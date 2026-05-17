# EDGE FEATURE CLASSIFIER — one phrase -> fase or rundung
#
# SYSTEM_PROMPT wird aus der Konventions-Bibliothek (ADR 0014 W2)
# zusammengesetzt. Kantenfeatures haben keine Positionierungs-Konvention
# (kein abstand_/kante_/Ecken-Regel) — nur seite + json_only sind geteilt.

from src.utils.prompt_loader import load_convention

_SEITE = load_convention("seite")
_JSON_ONLY = load_convention("json_only")


SYSTEM_PROMPT = f"""Du klassifizierst genau EINE CAD-Aktions-Phrase fuer Kantenfeatures:
Fasen und Rundungen.

Antwort: striktes JSON mit den Feldern typ, seite, parameter_hints.

typ:
  fase | rundung

{_SEITE}

parameter_hints:
  Nur explizite Zahlen aus der Phrase.
  Erlaubte Keys:
    groesse, radius, kantenlaenge

Regeln:
  "fase 2mm" -> typ "fase", groesse: 2.
  "radius 3mm", "abrunden", "rundung" -> typ "rundung", radius: 3.
  Keine Bohrungs-, Taschen- oder Nut-Parameter ausgeben.

{_JSON_ONLY}"""


CLASSIFIER_TEMPLATE = """\
TEIL-TYP: {teil_type}
TEIL-MASSE: {teil_params}
PARENT-PHRASE: {parent_phrase}

PHRASE:
{phrase}

JSON:"""
