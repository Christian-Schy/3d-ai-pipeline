# POCKET CLASSIFIER — one phrase -> tasche classification
#
# SYSTEM_PROMPT wird aus der Konventions-Bibliothek (ADR 0014 W2)
# zusammengesetzt: klassifizierer-spezifischer Kopf + geteilte Fragmente
# aus data/prompts/conventions/. Eine Konvention aendern = eine Datei dort.

from src.utils.prompt_loader import load_convention

# NOTE (W5): the `anker` fragment is intentionally NOT included here. In
# combination with `flaeche_positionierung` (kante_* edge-to-edge rule)
# the small models hang on long "Taschen-Kante ... vom Rand" phrases —
# both fragments compete for the same wording and the LLM stalls deciding
# which rule to apply. Pocket anchor cases (T_kombo etc.) therefore do
# NOT receive a classifier-emitted anker hint. The unit tests for pocket
# anchors inject anker_kind/anker_eltern through mocked parameter_hints;
# production pocket-on-pocket anchors are a follow-up (W3-style demo
# retraining or split prompt) — tracked as W5 follow-up in
# ADR 0014 §12.

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
    abstand_<richtung>, kante_<richtung>, versatz_<richtung>
      (oben/unten/rechts/links/vorne/hinten)

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
