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
  Nur Werte, die EXPLIZIT im Text stehen.
  Nicht raten, nicht rechnen, keine Defaults.
  Fast alle Hints sind Zahlen. Einzige String-Ausnahme:
    richtung: "x" | "y" | "z" fuer explizite Achsen in Nuten oder
              Bohrungsreihen ("entlang x", "entlang der Y-Achse").

  Dimensionen:
    durchmesser, tiefe, laenge, breite, hoehe, radius,
    kantenlaenge, groesse

  Position — Abstand vom Feature-Center zur Parent-Kante (DEFAULT):
    abstand_oben | abstand_unten | abstand_rechts | abstand_links |
    abstand_vorne | abstand_hinten
    Bedeutung: "von der oberen Kante 10mm entfernt" heisst: das ZENTRUM
    des Features ist 10mm von der Parent-Kante entfernt. (Konsistent
    mit der Bohrung-Konvention.)
    z.B. "von oberer Kante 10mm entfernt"        → abstand_oben: 10
         "von der rechten Seite 25mm entfernt"   → abstand_rechts: 25

  Position — Kante-zu-Kante (EXPLIZIT):
    kante_oben | kante_unten | kante_rechts | kante_links |
    kante_vorne | kante_hinten
    Bedeutung: nur wenn die Phrase BEIDE Kanten benennt — die KANTE des
    Features UND die Kante des Parents. Dann ist es edge-to-edge:
    Feature-Kante X mm von Parent-Kante.

    Erkennungsmuster (EINS davon reicht):
      a) "die <seite> Kante/Seite [der Tasche/des Slots]
          von <seite> X mm entfernt"  — Nominativ + zweite Praeposition.
      b) Wiederholtes Seiten-Wort vor und nach "von":
         "die UNTERE Seite von UNTEN X mm" / "die OBERE Seite von OBEN X mm".
         Auch ohne "Tasche/Slot"-Qualifier: das wiederholte Seiten-Wort
         IST schon der Hinweis "Pocket-Kante UND Cube-Kante".

    !! WICHTIG: "Kante" und "Seite" sind hier AUSTAUSCHBAR !!
    "die untere Seite von unten 10mm" ist genauso edge-to-edge wie
    "die untere Kante von unten 10mm". Beides → kante_unten: 10.

    Gegenbeispiele (NUR Cube-Kante, also DEFAULT abstand_*):
      "von der rechten Seite 25mm entfernt"        → abstand_rechts: 25
      "von oben 10mm entfernt"                     → abstand_oben: 10
      Praefix-"von" + KEINE wiederholte Pocket-Kante = abstand_*.

    Beispiele edge-to-edge:
      "die obere Kante von oben 10mm entfernt"     → kante_oben: 10
      "die linke Seite von links 10mm entfernt"    → kante_links: 10
      "die untere Seite von unten 10mm entfernt"   → kante_unten: 10
      "untere Kante der Tasche von unten 20mm"     → kante_unten: 20

    Bei Bohrungen (Kreis ohne rect-Edge) bleibt es bei abstand_*.

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

  richtung — Achse fuer lineare Features:
    Nur wenn explizit im Text genannt:
      "entlang x" / "entlang der X-Achse" → richtung: "x"
      "entlang y" / "entlang der Y-Achse" → richtung: "y"
      "entlang z" / "entlang der Z-Achse" → richtung: "z"
    Nicht aus Seiten oder Bauteilmassen ableiten.

  Pro Achse genau EIN Hint: abstand_* ODER kante_* ODER versatz_*.
  Mischformen ueber zwei Achsen sind erlaubt (z.B. abstand_oben +
  kante_links).

Mehrere Side-Woerter in einer Phrase ("oben soll unten rechts ..."):
  Das ERSTE bare Side-Wort in der Phrase ist die FACE-Auswahl. Spaetere
  Side-Woerter beschreiben die POSITION auf dieser Face — uebersetze sie
  in abstand_<seite> oder versatz_<seite>, NICHT in seite=...
  z.B. "oben soll unten rechts eine Bohrung von den Kanten 10mm entfernt"
       → seite=oben, abstand_unten=10, abstand_rechts=10
       (NICHT seite=unten oder seite=rechts.)
  "jeweils von den Kanten" auf einer Bohrung meint die Kanten passend
  zu den Position-Side-Woertern: "unten rechts ... 10mm" → 10mm Abstand
  zur unteren UND zur rechten Kante.

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
            "parameter_hints": {"breite": 5, "tiefe": 5, "laenge": 80,
                                "richtung": "x"},
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
        # EXPLIZITES edge-to-edge: beide Phrasen nennen die Pocket-Kante
        # ("die obere Kante" / "die linke Seite") UND die Cube-Kante.
        "phrase": "oben eine Tasche 20x30x10 die obere Kante von oben 10mm entfernt die linke Seite von links 10mm entfernt",
        "teil_type": "box",
        "teil_params": {"x": 200, "y": 200, "z": 200},
        "parent_phrase": "(keine)",
        "output": {
            "typ": "tasche",
            "seite": "oben",
            "parameter_hints": {"laenge": 20, "breite": 30, "tiefe": 10,
                                "kante_oben": 10, "kante_links": 10},
        },
    },
    {
        # DEFAULT abstand_* — Phrase nennt NUR die Cube-Kante, nicht die
        # Pocket-Kante ("von der rechten Seite 25mm entfernt"). Center-zu-Cube-Edge.
        "phrase": "oben eine Tasche 40x40x10 von der rechten Seite 25mm entfernt von der unteren Seite 25mm entfernt",
        "teil_type": "box",
        "teil_params": {"x": 200, "y": 200, "z": 200},
        "parent_phrase": "(keine)",
        "output": {
            "typ": "tasche",
            "seite": "oben",
            "parameter_hints": {"laenge": 40, "breite": 40, "tiefe": 10,
                                "abstand_rechts": 25, "abstand_unten": 25},
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
        # EXPLIZITES edge-to-edge mit "Seite" statt "Kante" — Run e3ddd2d0
        # phrase 2: "die untere Seite von unten 10mm" wurde faelschlicherweise
        # als abstand_unten klassifiziert. "Seite" und "Kante" sind hier
        # gleichwertig: die wiederholte Seiten-Erwaehnung ("untere ... von
        # unten") ist DAS Erkennungsmerkmal.
        "phrase": "oben eine Tasche 30x20x10 von der linken Seite 20mm entfernt die untere Seite von unten 10mm entfernt",
        "teil_type": "box",
        "teil_params": {"x": 200, "y": 200, "z": 200},
        "parent_phrase": "(keine)",
        "output": {
            "typ": "tasche",
            "seite": "oben",
            "parameter_hints": {"laenge": 30, "breite": 20, "tiefe": 10,
                                "abstand_links": 20, "kante_unten": 10},
        },
    },
    {
        # Edge-to-edge + Rotation gemischt
        "phrase": "vorne eine Tasche 20x30x10 die obere Kante von oben 10mm entfernt die linke Seite von links 10mm entfernt gegen Uhrzeigersinn um 20grad rotiert",
        "teil_type": "box",
        "teil_params": {"x": 200, "y": 200, "z": 200},
        "parent_phrase": "(keine)",
        "output": {
            "typ": "tasche",
            "seite": "vorne",
            "parameter_hints": {"laenge": 20, "breite": 30, "tiefe": 10,
                                "kante_oben": 10, "kante_links": 10,
                                "rotation_deg": 20},
        },
    },
    {
        # FACE-ZUERST-Pattern (Run f28b958a phrase_idx=1): "oben soll
        # unten rechts ..." — der erste bare Side-Term (oben) ist die
        # FACE, "unten rechts" beschreiben die Position auf der Face.
        # NICHT als seite=unten klassifizieren! "jeweils von den kanten
        # 10mm entfernt" auf einer Bohrung meint abstand_unten=10 +
        # abstand_rechts=10 (point-like, edge-to-center).
        "phrase": "oben soll unten rechts eine 18mm Bohrung jeweils von den Kanten 10mm entfernt mit 10mm Tiefe hin",
        "teil_type": "box",
        "teil_params": {"x": 200, "y": 200, "z": 200},
        "parent_phrase": "(keine)",
        "output": {
            "typ": "bohrung",
            "seite": "oben",
            "parameter_hints": {"durchmesser": 18, "tiefe": 10,
                                "abstand_unten": 10, "abstand_rechts": 10},
        },
    },
    {
        # Nested Bohrung in einer Tasche — Bohrungen sind point-like
        # (Kreis ohne rect-Extent), bleiben bei abstand_* (edge-to-center).
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
