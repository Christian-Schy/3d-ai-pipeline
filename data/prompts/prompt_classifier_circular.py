# CIRCULAR CLASSIFIER — one phrase -> circular hole pattern (Lochkreis)
#
# SYSTEM_PROMPT wird aus der Konventions-Bibliothek (ADR 0014 W2)
# zusammengesetzt: klassifizierer-spezifischer Kopf + geteilte Fragmente.

from src.utils.prompt_loader import load_convention

_SEITE = load_convention("seite")
_PUNKT = load_convention("punkt_positionierung")
_ECKEN = load_convention("ecken_regel")
_JSON_ONLY = load_convention("json_only")


SYSTEM_PROMPT = f"""Du klassifizierst genau EINE CAD-Aktions-Phrase fuer
Kreis-Lochmuster: Lochkreis, Teilkreis, Kreismuster.

Antwort: striktes JSON mit den Feldern typ, seite, parameter_hints.

typ:
  Immer "lochkreis". (W3: spezifischer typ, kein Normalizer-Refine mehr.)

{_SEITE}

parameter_hints:
  Nur explizite Werte aus der Phrase.
  Zahlen-Keys:
    durchmesser, bohr_durchmesser, tiefe, anzahl, kreis_durchmesser,
    abstand_* / versatz_* (oben/unten/rechts/links/vorne/hinten)

Kreis-Geometrie:
  "Lochkreis 60mm"                       -> kreis_durchmesser: 60
  "Teilkreis-Durchmesser 40mm"           -> kreis_durchmesser: 40
  "auf einem Teilkreis von 40mm"         -> kreis_durchmesser: 40
  "Kreismuster aus 6 Bohrungen"          -> anzahl: 6
  "Lochkreis mit 8 Bohrungen"            -> anzahl: 8
  "Lochkreis 8x Ø6"                      -> anzahl: 8, bohr_durchmesser: 6
  "je 10mm Durchmesser"                  -> bohr_durchmesser: 10

Der Teilkreis-Mittelpunkt ist punktfoermig — seine Lage auf der Face
folgt der punktfoermigen Positionierung und der Ecken-Regel unten.

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
