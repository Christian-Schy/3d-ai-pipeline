"""Prompt fuer den PocketChildPlacer-Agent.

Aufgabe: Aus dem User-Text saemtliche Bohrungen / Sub-Features herausziehen,
die INNERHALB einer Tasche platziert werden sollen, und sie als
Feature-in-Feature-Eintraege liefern (parent = Pocket-ID, Position
ist im Pocket-Lokalframe gemeint).

Der Agent ist ein 9b/26b-Schritt mit EINEM klaren Ziel — er soll keine
neuen Taschen erfinden und keine Teile umorganisieren. Er liest:
  1. User-Text
  2. Liste der bereits identifizierten Taschen mit ihrer Position-Hint
und liefert nur die Bohrungen-in-Taschen.
"""

SYSTEM_PROMPT = """Du extrahierst BOHRUNGEN-IN-TASCHEN aus einer CAD-Spezifikation.

Du kriegst:
  - Den User-Text
  - Eine LISTE bereits bekannter Taschen (id, parent_part, position_hint, x, y, depth)

Du lieferst:
  - Eine LISTE von Bohrungen, die INNERHALB einer Tasche sitzen, im JSON-Format

REGELN:
1. Erfinde NIE Taschen. Du arbeitest nur mit den vorgegebenen Pocket-IDs.
2. Erfinde NIE Bohrungen die NICHT explizit in der Tasche sitzen sollen.
3. Bei mehreren Taschen: Disambiguiere ueber Position-Hint
   (linke/rechte/zentrale/obere/untere Tasche).
4. Default-Position: zentriert (alignment="centered", keine edge_distances).
5. Bei "links 5/oben 5" oder "von der linken Kante 5mm": edge_distances setzen.
6. depth_reference IMMER "pocket_floor" — die Bohrung beginnt am Taschenboden.
7. Wenn unsicher zu welcher Tasche: lieber NICHTS extrahieren als raten.

OUTPUT-FORMAT (NUR JSON, keine Erklaerungen):
{
  "pocket_holes": [
    {
      "feature_id": "hole_in_pocket_1",
      "parent_pocket_id": "pocket_1",
      "type": "hole_single",
      "params": {"diameter": 8, "depth": 5},
      "position": {
        "side": "oben",
        "alignment": "centered",
        "edge_distances": null,
        "depth_reference": "pocket_floor"
      },
      "source_text": "Original-Schnipsel aus dem User-Text"
    }
  ]
}

Wenn KEINE Bohrung in einer Tasche beschrieben wird: {"pocket_holes": []}.
"""


POCKET_CHILD_PROMPT_TEMPLATE = """USER-SPEZIFIKATION:
{specification}

VERFUEGBARE TASCHEN:
{pockets_listing}

Extrahiere alle Bohrungen, die INNERHALB einer dieser Taschen platziert werden sollen.
Antworte NUR mit JSON nach dem oben genannten Schema.
"""


# Few-Shots fuer DSPy / Seed
FEW_SHOT_EXAMPLES = [
    {
        "spec": "Wuerfel 100x100x50, Tasche zentral 40x40 tief 10, in der Tasche eine Bohrung Durchmesser 8 tief 5",
        "pockets": [
            {"id": "pocket_1", "parent_part": "wuerfel", "position_hint": "zentral",
             "x": 40, "y": 40, "depth": 10},
        ],
        "output": {
            "pocket_holes": [
                {
                    "feature_id": "hole_in_pocket_1",
                    "parent_pocket_id": "pocket_1",
                    "type": "hole_single",
                    "params": {"diameter": 8, "depth": 5},
                    "position": {
                        "side": "oben",
                        "alignment": "centered",
                        "edge_distances": None,
                        "depth_reference": "pocket_floor",
                    },
                    "source_text": "in der Tasche eine Bohrung Durchmesser 8 tief 5",
                }
            ]
        },
    },
    {
        "spec": "Platte 80x80x10, links eine Tasche 20x20 tief 5, rechts eine Tasche 30x30 tief 6, in der linken Tasche zentral eine Bohrung d=4 tief 3",
        "pockets": [
            {"id": "pocket_links", "parent_part": "platte", "position_hint": "links",
             "x": 20, "y": 20, "depth": 5},
            {"id": "pocket_rechts", "parent_part": "platte", "position_hint": "rechts",
             "x": 30, "y": 30, "depth": 6},
        ],
        "output": {
            "pocket_holes": [
                {
                    "feature_id": "hole_in_pocket_links_1",
                    "parent_pocket_id": "pocket_links",
                    "type": "hole_single",
                    "params": {"diameter": 4, "depth": 3},
                    "position": {
                        "side": "oben",
                        "alignment": "centered",
                        "edge_distances": None,
                        "depth_reference": "pocket_floor",
                    },
                    "source_text": "in der linken Tasche zentral eine Bohrung d=4 tief 3",
                }
            ]
        },
    },
    {
        "spec": "Wuerfel 100mm, Tasche oben 30x30 tief 8, in der Tasche links 5 oben 5 eine Bohrung d=5 tief 4",
        "pockets": [
            {"id": "pocket_1", "parent_part": "wuerfel", "position_hint": "oben",
             "x": 30, "y": 30, "depth": 8},
        ],
        "output": {
            "pocket_holes": [
                {
                    "feature_id": "hole_in_pocket_1",
                    "parent_pocket_id": "pocket_1",
                    "type": "hole_single",
                    "params": {"diameter": 5, "depth": 4},
                    "position": {
                        "side": "oben",
                        "alignment": "centered",
                        "edge_distances": {"left": 5, "top": 5},
                        "depth_reference": "pocket_floor",
                    },
                    "source_text": "in der Tasche links 5 oben 5 eine Bohrung d=5 tief 4",
                }
            ]
        },
    },
    {
        "spec": "Wuerfel 60mm mit einer Bohrung d=10 oben",
        "pockets": [],
        "output": {"pocket_holes": []},
    },
]
