# SLOT CLASSIFIER — one phrase -> nut classification
#
# SYSTEM_PROMPT wird aus der Konventions-Bibliothek (ADR 0014 W2)
# zusammengesetzt: klassifizierer-spezifischer Kopf + geteilte Fragmente.

from src.utils.prompt_loader import load_convention

# NOTE (W5): like pocket, slot uses `flaeche_positionierung` (kante_*).
# The anker fragment conflicts with that on phrases mentioning "Nut-Kante";
# we leave it out here so the small classifier model does not stall on
# long edge-to-edge wordings. Slot anchors are covered by unit-test
# mocks; production slot-on-parent anchors are a W5 follow-up.

_SEITE = load_convention("seite")
_FLAECHE = load_convention("flaeche_positionierung")
_ECKEN = load_convention("ecken_regel")
_ROTATION = load_convention("rotation")
_JSON_ONLY = load_convention("json_only")


SYSTEM_PROMPT = f"""Du klassifizierst genau EINE CAD-Aktions-Phrase fuer Nuten/Slots.

Antwort: striktes JSON mit den Feldern typ, seite, parameter_hints.

typ:
  Immer "nut".

{_SEITE}

parameter_hints:
  Erlaubte Werte aus der Phrase.
  Zahlen-Keys:
    laenge, breite, tiefe, rotation_deg
    abstand_*, kante_*, versatz_* (oben/unten/rechts/links/vorne/hinten)
    anfang_*, ende_*  (oben/unten/rechts/links/vorne/hinten)
  String-Key:
    richtung: "x" | "y" | "z" wenn explizit "entlang x/y/z" oder
      "entlang der X/Y/Z-Achse" genannt ist.

{_FLAECHE}

Anfangs-/Endpunkt-Modell:
  Ist die Nut ueber ZWEI Endpunkte statt eine Laenge beschrieben
  ("Anfangspunkt 20mm von linker Kante, Endpunkt 80mm von linker
  Kante"), gib anfang_<kante> und ende_<kante> aus -- beide an
  derselben Bezugskante, KEIN laenge-Key.
    "anfangspunkt 20mm von linker kante endpunkt 80mm von linker kante"
      -> anfang_links: 20, ende_links: 80
  Achse aus den Endpunkten ableiten:
    Endpunkte an linker/rechter Kante  -> richtung: "x".
    Endpunkte an vorderer/hinterer Kante -> richtung: "y".
  Nicht rechnen: gib die rohen Endpunkt-Distanzen aus, der deterministische
  FeatureBuilder bildet daraus die Laenge -- NICHT laenge = ende - anfang.

{_ECKEN}

{_ROTATION}

{_JSON_ONLY}"""


CLASSIFIER_TEMPLATE = """\
TEIL-TYP: {teil_type}
TEIL-MASSE: {teil_params}
PARENT-PHRASE: {parent_phrase}

PHRASE:
{phrase}

JSON:"""
