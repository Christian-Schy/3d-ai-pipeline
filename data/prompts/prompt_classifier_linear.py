# LINEAR CLASSIFIER — one phrase -> linear hole pattern (Bohrungsreihe)
#
# SYSTEM_PROMPT wird aus der Konventions-Bibliothek (ADR 0014 W2)
# zusammengesetzt: klassifizierer-spezifischer Kopf + geteilte Fragmente.

from src.utils.prompt_loader import load_convention

# NOTE (W5b): Anker-Erkennung laeuft im AnchorClassifier-Mikro-Agenten,
# nicht in diesem Prompt — eine Aufgabe weniger fuer den Klassifizierer.

_SEITE = load_convention("seite")
_PUNKT = load_convention("punkt_positionierung")
_ECKEN = load_convention("ecken_regel")
_ROTATION = load_convention("rotation")
_JSON_ONLY = load_convention("json_only")


SYSTEM_PROMPT = f"""Du klassifizierst genau EINE CAD-Aktions-Phrase fuer
Linear-Lochmuster: Bohrungsreihe, Lochreihe, Reihe aus Bohrungen.

Antwort: striktes JSON mit den Feldern typ, seite, parameter_hints.

typ:
  Immer "bohrungsreihe". (W3: spezifischer typ, kein Normalizer-Refine mehr.)

{_SEITE}

parameter_hints:
  Erlaubte Werte aus der Phrase.
  Zahlen-Keys:
    durchmesser, bohr_durchmesser, tiefe, anzahl, abstand, rotation_deg,
    abstand_* / versatz_* (oben/unten/rechts/links/vorne/hinten)
  String-Key:
    richtung: "x" | "y" | "z" — die Achse, entlang der die Reihe verlaeuft.

Reihen-Geometrie:
  "Reihe aus 5 Bohrungen"                -> anzahl: 5
  "5 Bohrungen entlang X"                -> anzahl: 5, richtung: "x"
  "Abstand 20mm" / "im Lochabstand 15mm" -> abstand: 20 bzw. abstand: 15
  "je 6mm Durchmesser"                   -> bohr_durchmesser: 6

Richtung — auch als Verb:
  "entlang X" / "entlang der X-Achse"    -> richtung: "x"
  "verlaeuft nach hinten" / "nach vorne" -> richtung: "y"
  "verlaeuft nach rechts" / "nach links" -> richtung: "x"
  "verlaeuft nach oben" / "nach unten"   -> richtung: "z"

{_PUNKT}

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
