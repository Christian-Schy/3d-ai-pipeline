# GRID CLASSIFIER — one phrase -> grid hole pattern (Raster / Eckbohrungen)
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
Raster-Lochmuster (Grid) und Eckbohrungen.

Antwort: striktes JSON mit den Feldern typ, seite, parameter_hints.

typ:
  Immer "eckbohrungen". (W3: dieser Klassifizierer ist fuer Raster und
  Eckbohrungen zustaendig — beide laufen downstream auf hole_pattern_grid.
  Die Unterscheidung Explizites-Raster vs. Eckbohrungen steckt in den
  Parametern, nicht im typ.)

{_SEITE}

★★★ KERN-UNTERSCHEIDUNG — zwei Grid-Arten:

1) EXPLIZITES RASTER — die Phrase nennt einen RASTERABSTAND
   (Worte: "Rasterabstand", "Lochabstand", "Raster ... Abstand").
   Dann emittiere rows, cols UND den Rasterabstand.
     "Lochmuster 4x3, Rasterabstand 25mm" -> rows: 4, cols: 3, rasterabstand: 25
     "Raster 3x3 mit 30mm Lochabstand"     -> rows: 3, cols: 3, rasterabstand: 30
     "Lochmuster 4x2, Rasterabstand 20mm in X und 30mm in Y"
        -> rows: 4, cols: 2, rasterabstand_x: 20, rasterabstand_y: 30
   Die ERSTE Zahl von "NxM" ist rows, die zweite cols.

2) ECKBOHRUNGEN — die Phrase nennt einen RANDABSTAND zur Kante
   ("von den Kanten X mm entfernt", "Randabstand X mm zur Kante",
   "an jeder Ecke") und KEINEN Rasterabstand.
   Dann emittiere anzahl und abstand_kante. NIEMALS rows/cols hier!
     "4 Eckbohrungen jeweils 20mm von den Kanten" -> anzahl: 4, abstand_kante: 20
     "2x2 Lochmuster, Randabstand 10mm zur Kante" -> anzahl: 4, abstand_kante: 10

  Merke: "2x2 Lochmuster" OHNE Rasterabstand sind 4 Eckbohrungen
  (anzahl: 4, abstand_kante). rows/cols NUR wenn ein Rasterabstand
  ausdruecklich genannt ist.

parameter_hints:
  Erlaubte Werte aus der Phrase.
  Zahlen-Keys:
    durchmesser, bohr_durchmesser, tiefe,
    rows, cols, rasterabstand, rasterabstand_x, rasterabstand_y,
    anzahl, abstand_kante, rotation_deg,
    abstand_* / versatz_* (oben/unten/rechts/links/vorne/hinten)
  "je 6mm Durchmesser" -> durchmesser: 6.

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
