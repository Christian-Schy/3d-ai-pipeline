# AKTIONS-KLASSIFIZIERER — System Prompt
# Aufgabe: EINE einzelne Aktions-Phrase (vom Aktions-Splitter geliefert)
# in {typ, seite, parameter_hints} klassifizieren.
#
# Prinzip aus ADR 0003: kleiner, fokussierter LLM-Call. Der Agent
# beschreibt die Aktion NICHT, er klassifiziert sie nur. Die teure
# Strukturierung in Features macht der feature_definierer (Stufe 3).
#
# Bewusst minimal gehalten — Memory feedback_split_complex_agents:
# "Lieber 1 Agent mehr als ueberladene Prompts — 9b halluziniert bei zu
# vielen Regeln pro Call".

SYSTEM_PROMPT = """Du klassifizierst genau EINE CAD-Aktions-Phrase.

Antwort: striktes JSON mit den Feldern typ, seite, parameter_hints.

typ:
  tasche  | bohrung | nut | fase | rundung
seite:
  oben | unten | rechts | links | vorne | hinten
parameter_hints (optional):
  Nur Zahlen, die EXPLIZIT im Text stehen.
  Beispiele: durchmesser, tiefe, laenge, breite, hoehe, radius,
             rotation_deg, kantenlaenge, groesse.
  Nicht raten, nicht rechnen, keine Defaults.

Verschachtelte Phrasen ("in der Tasche ..." / "darin ..."):
  Wenn die Phrase keine eigene Seite nennt, nutze die Seite des
  PARENT-Phrasen-Eintrags (steht im Kontext).

Antworte NUR mit dem JSON-Objekt. Kein Markdown, keine Erklaerung,
keine Liste."""


# Eingabe-Template fuer einen einzelnen Klassifizierungs-Call.
# parent_phrase ist "(keine)" fuer top-level Aktionen.
AKTIONS_KLASSIFIZIERER_TEMPLATE = """\
TEIL-TYP: {teil_type}
TEIL-MASSE: {teil_params}
PARENT-PHRASE: {parent_phrase}

PHRASE:
{phrase}

JSON:"""


# Few-Shot Beispiele — Reference fuer Modell-Verhalten und Trainings-Seed
# fuer DSPy. Drei top-level Aktionen + zwei nested Children.
FEW_SHOT_EXAMPLES = [
    {
        "phrase": "rechts eine Bohrung 8mm 10 tief",
        "teil_type": "box",
        "teil_params": {"x": 100, "y": 100, "z": 100},
        "parent_phrase": "(keine)",
        "output": {
            "typ": "bohrung",
            "seite": "rechts",
            "parameter_hints": {"durchmesser": 8, "tiefe": 10},
        },
    },
    {
        "phrase": "oben eine Tasche 60x40x10 um 10 grad gedreht",
        "teil_type": "box",
        "teil_params": {"x": 200, "y": 200, "z": 200},
        "parent_phrase": "(keine)",
        "output": {
            "typ": "tasche",
            "seite": "oben",
            "parameter_hints": {"laenge": 60, "breite": 40, "tiefe": 10,
                                "rotation_deg": 10},
        },
    },
    {
        "phrase": "in der Tasche eine 10mm Bohrung 10 tief",
        "teil_type": "box",
        "teil_params": {"x": 200, "y": 200, "z": 200},
        "parent_phrase": "oben eine Tasche 60x40x10 um 10 grad gedreht",
        "output": {
            "typ": "bohrung",
            "seite": "oben",
            "parameter_hints": {"durchmesser": 10, "tiefe": 10},
        },
    },
    {
        "phrase": "vorne eine Nut 5x5 entlang der x-achse 80mm lang",
        "teil_type": "box",
        "teil_params": {"x": 100, "y": 100, "z": 100},
        "parent_phrase": "(keine)",
        "output": {
            "typ": "nut",
            "seite": "vorne",
            "parameter_hints": {"breite": 5, "tiefe": 5, "laenge": 80},
        },
    },
    {
        "phrase": "an der oberen Kante eine Fase 2mm",
        "teil_type": "box",
        "teil_params": {"x": 80, "y": 80, "z": 40},
        "parent_phrase": "(keine)",
        "output": {
            "typ": "fase",
            "seite": "oben",
            "parameter_hints": {"groesse": 2},
        },
    },
]
