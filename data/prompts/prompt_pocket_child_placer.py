"""Prompt fuer den PocketChildPlacer-Agent.

Aufgabe (V2, ab 2026-05-05): NUR Containment-Erkennung. Der Agent ordnet
existierende Bohrungs-Features einer Tasche zu — er parst KEINE Position
mehr. Die Position kommt vom feature_definierer und wird vom Code 1:1
durchgereicht.

Hintergrund: in Run 965da548 hat der Agent beim Position-Parsen den
"10mm nach oben"-Versatz verloren, obwohl der feature_definierer ihn
korrekt als center_offset extrahiert hatte. Architektur-Entscheidung:
ein Agent, eine Aufgabe — Textverstaendnis "in welcher Tasche?" bleibt
LLM, Wert-Uebernahme ist deterministisch.
"""

SYSTEM_PROMPT = """Du ordnest BOHRUNGEN einer TASCHE zu (Containment-Mapping).

Du kriegst:
  - Den User-Text
  - Eine LISTE bereits bekannter Taschen (id, parent_part, position_hint, x, y, depth)
  - Eine LISTE bereits extrahierter Bohrungen (feature_id, durchmesser, tiefe, source_text)

Du lieferst:
  - Eine LISTE von Zuordnungen: welche Bohrung gehoert IN welche Tasche?

REGELN:
1. Erfinde NIE neue Bohrungen oder Taschen. Nur Mapping.
2. Eine Bohrung wird nur zugeordnet, wenn der User explizit sagt sie sitzt
   IN der Tasche ("in der Tasche", "in der Ausnehmung", "in der Vertiefung",
   "im Pocket", "innerhalb der Tasche", "am Taschenboden").
3. Bei mehreren Taschen: Disambiguiere ueber position_hint
   (linke/rechte/zentrale/obere/untere Tasche) und Reihenfolge.
4. Bei mehreren Bohrungen pro Tasche: gib alle in der Liste an.
5. Wenn unsicher: lieber NICHTS zuordnen als raten.
6. Du parst KEINE Positionen, KEINE Versaetze, KEINE Kantenabstaende.
   Diese Werte stehen schon in den Bohrungs-Features und werden vom
   Code uebernommen.

OUTPUT-FORMAT (NUR JSON, keine Erklaerungen):
{
  "assignments": [
    {
      "hole_feature_id": "bohrung_oben_1",
      "pocket_id": "pocket_1"
    }
  ]
}

Wenn KEINE Bohrung in einer Tasche sitzt: {"assignments": []}.
"""


POCKET_CHILD_PROMPT_TEMPLATE = """USER-SPEZIFIKATION:
{specification}

VERFUEGBARE TASCHEN:
{pockets_listing}

VERFUEGBARE BOHRUNGEN:
{holes_listing}

Welche dieser Bohrungen gehoert in welche Tasche? Antworte NUR mit JSON
nach dem oben genannten Schema. Keine Position parsen — nur Zuordnung.
"""


# Few-Shots fuer DSPy / Seed
FEW_SHOT_EXAMPLES = [
    {
        "spec": "Wuerfel 100x100x50, Tasche zentral 40x40 tief 10, in der Tasche eine Bohrung Durchmesser 8 tief 5",
        "pockets": [
            {"id": "pocket_1", "parent_part": "wuerfel", "position_hint": "zentral",
             "x": 40, "y": 40, "depth": 10},
        ],
        "holes": [
            {"feature_id": "bohrung_oben_1", "durchmesser": 8, "tiefe": 5,
             "source_text": "in der Tasche eine Bohrung Durchmesser 8 tief 5"},
        ],
        "output": {
            "assignments": [
                {"hole_feature_id": "bohrung_oben_1", "pocket_id": "pocket_1"},
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
        "holes": [
            {"feature_id": "bohrung_oben_1", "durchmesser": 4, "tiefe": 3,
             "source_text": "in der linken Tasche zentral eine Bohrung d=4 tief 3"},
        ],
        "output": {
            "assignments": [
                {"hole_feature_id": "bohrung_oben_1", "pocket_id": "pocket_links"},
            ]
        },
    },
    {
        "spec": "Wuerfel 200, oben eine Tasche 60x40 tief 10, in der Tasche 15 nach rechts und 10 nach oben eine Bohrung d=10 tief 10, in der Tasche zusaetzlich von der linken Kante 10 von der oberen 10 eine Bohrung d=10 tief 10",
        "pockets": [
            {"id": "tasche_oben_0", "parent_part": "wuerfel", "position_hint": "oben",
             "x": 60, "y": 40, "depth": 10},
        ],
        "holes": [
            {"feature_id": "bohrung_oben_1", "durchmesser": 10, "tiefe": 10,
             "source_text": "in der Tasche 15 nach rechts und 10 nach oben eine Bohrung d=10 tief 10"},
            {"feature_id": "bohrung_oben_2", "durchmesser": 10, "tiefe": 10,
             "source_text": "in der Tasche zusaetzlich von der linken Kante 10 von der oberen 10 eine Bohrung d=10 tief 10"},
        ],
        "output": {
            "assignments": [
                {"hole_feature_id": "bohrung_oben_1", "pocket_id": "tasche_oben_0"},
                {"hole_feature_id": "bohrung_oben_2", "pocket_id": "tasche_oben_0"},
            ]
        },
    },
    {
        "spec": "Wuerfel 60mm mit einer Bohrung d=10 oben",
        "pockets": [],
        "holes": [
            {"feature_id": "bohrung_oben_1", "durchmesser": 10, "tiefe": 10,
             "source_text": "Bohrung d=10 oben"},
        ],
        "output": {"assignments": []},
    },
    {
        "spec": "Platte mit Tasche 40x40 zentral, davor eine Bohrung d=6",
        "pockets": [
            {"id": "pocket_1", "parent_part": "platte", "position_hint": "zentral",
             "x": 40, "y": 40, "depth": 5},
        ],
        "holes": [
            {"feature_id": "bohrung_oben_1", "durchmesser": 6, "tiefe": 10,
             "source_text": "davor eine Bohrung d=6"},
        ],
        "output": {"assignments": []},
    },
]
