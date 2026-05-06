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
  Nicht raten, nicht rechnen, keine Defaults.

  Dimensionen:
    durchmesser, tiefe, laenge, breite, hoehe, radius,
    kantenlaenge, groesse

  Position — Abstand von einer Kante nach innen:
    abstand_oben | abstand_unten | abstand_rechts | abstand_links |
    abstand_vorne | abstand_hinten
    z.B. "von oberer Kante 10mm entfernt"        → abstand_oben: 10
         "die linke Seite von links 10mm entfernt" → abstand_links: 10

  Position — Versatz von der Mitte in eine Richtung:
    versatz_oben | versatz_unten | versatz_rechts | versatz_links |
    versatz_vorne | versatz_hinten
    z.B. "20mm nach oben versetzt"   → versatz_oben: 20
         "10mm nach rechts versetzt" → versatz_rechts: 10
         "nach links um 5mm"         → versatz_links: 5

  rotation_deg — Vorzeichen-Konvention (CadQuery: positiv = CCW):
    "gegen Uhrzeigersinn" / "linksdrehend" / "CCW" → POSITIV
    "im Uhrzeigersinn"    / "rechtsdrehend" / "CW" → NEGATIV
    Keine Richtung genannt → positiv (Standard CCW).

  abstand_* und versatz_* sind exklusiv: ein und dieselbe Achse hat
  entweder einen Kanten-Abstand ODER einen Mitten-Versatz, nie beides.

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
    {
        "phrase": "vorne eine Tasche 30x20x10 um 20 grad im Uhrzeigersinn gedreht",
        "teil_type": "box",
        "teil_params": {"x": 200, "y": 200, "z": 200},
        "parent_phrase": "(keine)",
        "output": {
            "typ": "tasche",
            "seite": "vorne",
            "parameter_hints": {"laenge": 30, "breite": 20, "tiefe": 10,
                                "rotation_deg": -20},
        },
    },
    {
        "phrase": "rechts eine Tasche 20x30x10 gegen Uhrzeigersinn um 20grad rotiert",
        "teil_type": "box",
        "teil_params": {"x": 200, "y": 200, "z": 200},
        "parent_phrase": "(keine)",
        "output": {
            "typ": "tasche",
            "seite": "rechts",
            "parameter_hints": {"laenge": 20, "breite": 30, "tiefe": 10,
                                "rotation_deg": 20},
        },
    },
    {
        # Edge-distances — beide Achsen haben einen Kanten-Abstand
        "phrase": "oben eine Tasche 20x30x10 die obere Kante von oben 10mm entfernt die linke Seite von links 10mm entfernt",
        "teil_type": "box",
        "teil_params": {"x": 200, "y": 200, "z": 200},
        "parent_phrase": "(keine)",
        "output": {
            "typ": "tasche",
            "seite": "oben",
            "parameter_hints": {"laenge": 20, "breite": 30, "tiefe": 10,
                                "abstand_oben": 10, "abstand_links": 10},
        },
    },
    {
        # Center-offsets — beide Achsen sind von der Mitte versetzt
        "phrase": "oben eine Tasche 30x20x10 nach oben um 20mm nach rechts um 20mm versetzt",
        "teil_type": "box",
        "teil_params": {"x": 200, "y": 200, "z": 200},
        "parent_phrase": "(keine)",
        "output": {
            "typ": "tasche",
            "seite": "oben",
            "parameter_hints": {"laenge": 30, "breite": 20, "tiefe": 10,
                                "versatz_oben": 20, "versatz_rechts": 20},
        },
    },
    {
        # Edge-distances + Rotation gemischt
        "phrase": "vorne eine Tasche 20x30x10 die obere Kante von oben 10mm entfernt die linke Seite von links 10mm entfernt gegen Uhrzeigersinn um 20grad rotiert",
        "teil_type": "box",
        "teil_params": {"x": 200, "y": 200, "z": 200},
        "parent_phrase": "(keine)",
        "output": {
            "typ": "tasche",
            "seite": "vorne",
            "parameter_hints": {"laenge": 20, "breite": 30, "tiefe": 10,
                                "abstand_oben": 10, "abstand_links": 10,
                                "rotation_deg": 20},
        },
    },
    {
        # Nested Bohrung — Edge-distances in der Tasche, Seite vom Parent geerbt
        "phrase": "in der Tasche von links 10mm und von der oberen Kante 10mm entfernt 18mm Bohrung 10tief",
        "teil_type": "box",
        "teil_params": {"x": 200, "y": 200, "z": 200},
        "parent_phrase": "links eine Tasche 30x20x10 von der linken Seite 20mm entfernt",
        "output": {
            "typ": "bohrung",
            "seite": "links",
            "parameter_hints": {"durchmesser": 18, "tiefe": 10,
                                "abstand_links": 10, "abstand_oben": 10},
        },
    },
]
