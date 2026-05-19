# CIRCULAR CLASSIFIER — one phrase -> circular hole pattern (Lochkreis)
#
# SYSTEM_PROMPT wird aus der Konventions-Bibliothek (ADR 0014 W2)
# zusammengesetzt: klassifizierer-spezifischer Kopf + geteilte Fragmente.

from src.utils.prompt_loader import load_convention

# NOTE (W5b): Anker-Erkennung laeuft im AnchorClassifier-Mikro-Agenten,
# nicht in diesem Prompt — eine Aufgabe weniger fuer den Klassifizierer.

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
  Erlaubte Werte aus der Phrase.
  Zahlen-Keys:
    durchmesser, bohr_durchmesser, tiefe, anzahl, kreis_durchmesser,
    startwinkel,
    abstand_* / versatz_* (oben/unten/rechts/links/vorne/hinten)

Kreis-Geometrie:
  "Lochkreis 60mm"                       -> kreis_durchmesser: 60
  "Teilkreis-Durchmesser 40mm"           -> kreis_durchmesser: 40
  "auf einem Teilkreis von 40mm"         -> kreis_durchmesser: 40
  "Kreismuster aus 6 Bohrungen"          -> anzahl: 6
  "Lochkreis mit 8 Bohrungen"            -> anzahl: 8
  "Lochkreis 8x Ø6"                      -> anzahl: 8, bohr_durchmesser: 6
  "je 10mm Durchmesser"                  -> bohr_durchmesser: 10

Startwinkel (optional, Default 0 = erste Bohrung bei 3 Uhr / +X-Achse):
  "erste Bohrung bei 0 Grad"             -> startwinkel: 0
  "erste Bohrung bei 90 Grad"            -> startwinkel: 90
  "erste Bohrung oben"                   -> startwinkel: 90
  "Lochkreis um 30 Grad gedreht"         -> startwinkel: 30
  "Startwinkel 45 Grad"                  -> startwinkel: 45
  Konvention: CCW positiv, 0 = +X (3 Uhr), 90 = +Y (12 Uhr).

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
