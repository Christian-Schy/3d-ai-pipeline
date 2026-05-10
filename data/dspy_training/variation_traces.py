"""
variation_traces.py - hand-curated language variation pack.

Purpose:
  - Broaden training coverage with phrasing variants that are likely in
    voice input or from users who do not phrase CAD specs like the project
    author.
  - Keep language understanding in LLM agents. These examples are training
    material, not new deterministic parsing rules.

Coverage in this first pack:
  - Part/dimension order variants: "bei einem 200mm Wuerfel",
    "Wuerfel mit 75mm", "mit den Massen ...", "200er Wuerfel".
  - Missing comma between part declaration and first feature.
  - Edge-distance wording variants: Abstand/Entfernung/von der Kante/von der
    Seite, with values other than 10mm.
  - Center-offset wording variants with explicit direction.

Deferred intentionally:
  - "nach aussen", "ragt raus", extrusion/additive overhang language needs a
    first-class schema/template path before it should become active training
    data. Otherwise we would teach outputs the pipeline cannot yet represent.
"""

from __future__ import annotations

import json
import sys


def _pos(side: str = "oben", alignment: str = "centered",
         edge_distances: dict | None = None,
         angle_deg: float = 0.0, notes: str = "",
         center_offset: dict | None = None,
         pocket_edge_distances: dict | None = None) -> dict:
    pos = {
        "side": side,
        "alignment": alignment,
        "edge_distances": edge_distances,
        "angle_deg": angle_deg,
        "notes": notes,
    }
    if center_offset:
        pos["center_offset"] = center_offset
    if pocket_edge_distances:
        pos["pocket_edge_distances"] = pocket_edge_distances
    return pos


def _box_part(part_id: str, beschreibung: str, x: int, y: int, z: int) -> dict:
    return {
        "id": part_id,
        "type": "box",
        "beschreibung": beschreibung,
        "raw_params": {"x": x, "y": y, "z": z},
    }


TRACES: list[dict] = [
    {
        "id": "var_part_200mm_wuerfel_missing_comma",
        "specification": (
            "bei einem 200mm Wuerfel oben eine 12mm Bohrung "
            "18mm von der oberen Kante entfernt"
        ),
        "punctuation": {
            "raw": (
                "bei einem 200mm Wuerfel oben eine 12mm Bohrung "
                "18mm von der oberen Kante entfernt"
            ),
            "punctuated": (
                "bei einem 200mm Wuerfel, oben eine 12mm Bohrung "
                "18mm von der oberen Kante entfernt"
            ),
        },
        "metadata": {
            "difficulty": "P1",
            "category": "variation_part_dimension_order",
            "sprachstil": "natuerlich",
        },
        "inventar": {
            "teil_count": 1,
            "teile": [_box_part("wuerfel", "200mm Wuerfel", 200, 200, 200)],
            "aktionen": [{
                "teil_id": "wuerfel",
                "seite": "oben",
                "beschreibung": (
                    "12mm Bohrung 18mm von der oberen Kante entfernt"
                ),
            }],
        },
        "aktions_klassifizierer": [{
            "phrase": (
                "oben eine 12mm Bohrung 18mm von der oberen Kante entfernt"
            ),
            "teil_id": "wuerfel",
            "parent_phrase": "(keine)",
            "output": {
                "typ": "bohrung",
                "seite": "oben",
                "parameter_hints": {
                    "durchmesser": 12,
                    "abstand_oben": 18,
                },
            },
        }],
        "normalizer_pairs": [{
            "input": {
                "beschreibung": (
                    "12mm Bohrung 18mm von der oberen Kante entfernt"
                ),
                "seite": "oben",
                "teil_type": "box",
                "teil_params": {"x": 200, "y": 200, "z": 200},
            },
            "output": {
                "type": "hole_single",
                "params": {"diameter": 12, "depth": None},
                "position": _pos("oben", edge_distances={"top": 18}),
                "operation": "subtract",
            },
        }],
    },
    {
        "id": "var_part_wuerfel_mit_75mm",
        "specification": (
            "Wuerfel mit 75mm, auf der Oberseite ein Loch mit 9mm "
            "Durchmesser mittig"
        ),
        "metadata": {
            "difficulty": "P0",
            "category": "variation_part_dimension_order",
            "sprachstil": "natuerlich",
        },
        "inventar": {
            "teil_count": 1,
            "teile": [_box_part("wuerfel", "Wuerfel mit 75mm", 75, 75, 75)],
            "aktionen": [{
                "teil_id": "wuerfel",
                "seite": "oben",
                "beschreibung": "Loch mit 9mm Durchmesser mittig",
            }],
        },
        "aktions_klassifizierer": [{
            "phrase": "auf der Oberseite ein Loch mit 9mm Durchmesser mittig",
            "teil_id": "wuerfel",
            "parent_phrase": "(keine)",
            "output": {
                "typ": "bohrung",
                "seite": "oben",
                "parameter_hints": {"durchmesser": 9},
            },
        }],
    },
    {
        "id": "var_part_quader_mit_massen",
        "specification": (
            "ich brauche einen Quader mit den Massen 160 mal 80 mal 35, "
            "rechts eine Tasche 34 mal 22 und 7 tief"
        ),
        "metadata": {
            "difficulty": "P0",
            "category": "variation_part_dimension_order",
            "sprachstil": "umgangssprachlich",
        },
        "inventar": {
            "teil_count": 1,
            "teile": [_box_part("quader", "Quader 160x80x35", 160, 80, 35)],
            "aktionen": [{
                "teil_id": "quader",
                "seite": "rechts",
                "beschreibung": "Tasche 34 mal 22 und 7 tief",
            }],
        },
        "aktions_klassifizierer": [{
            "phrase": "rechts eine Tasche 34 mal 22 und 7 tief",
            "teil_id": "quader",
            "parent_phrase": "(keine)",
            "output": {
                "typ": "tasche",
                "seite": "rechts",
                "parameter_hints": {"laenge": 34, "breite": 22, "tiefe": 7},
            },
        }],
        "normalizer_pairs": [{
            "input": {
                "beschreibung": "Tasche 34 mal 22 und 7 tief",
                "seite": "rechts",
                "teil_type": "box",
                "teil_params": {"x": 160, "y": 80, "z": 35},
            },
            "output": {
                "type": "pocket_rect",
                "params": {"x": 34, "y": 22, "depth": 7},
                "position": _pos("rechts"),
                "operation": "subtract",
            },
        }],
    },
    {
        "id": "var_part_platte_200er_style",
        "specification": (
            "eine 200er Platte, 120 breit und 14 dick, oben eine 6er "
            "Bohrung 21mm von links"
        ),
        "metadata": {
            "difficulty": "P1",
            "category": "variation_part_dimension_order",
            "sprachstil": "umgangssprachlich",
        },
        "inventar": {
            "teil_count": 1,
            "teile": [_box_part("platte", "200x120x14 Platte", 200, 120, 14)],
            "aktionen": [{
                "teil_id": "platte",
                "seite": "oben",
                "beschreibung": "6er Bohrung 21mm von links",
            }],
        },
        "aktions_klassifizierer": [{
            "phrase": "oben eine 6er Bohrung 21mm von links",
            "teil_id": "platte",
            "parent_phrase": "(keine)",
            "output": {
                "typ": "bohrung",
                "seite": "oben",
                "parameter_hints": {
                    "durchmesser": 6,
                    "abstand_links": 21,
                },
            },
        }],
    },
    {
        "id": "var_edge_distance_abstand_entfernung",
        "specification": (
            "120x90x18 Platte, oben eine Bohrung mit 14mm Durchmesser, "
            "mit einem Abstand von 23mm von der oberen Seite und einer "
            "Entfernung von 31mm von der linken Kante"
        ),
        "metadata": {
            "difficulty": "P2",
            "category": "variation_edge_distance",
            "sprachstil": "technisch_ausfuehrlich",
        },
        "inventar": {
            "teil_count": 1,
            "teile": [_box_part("platte", "120x90x18 Platte", 120, 90, 18)],
            "aktionen": [{
                "teil_id": "platte",
                "seite": "oben",
                "beschreibung": (
                    "Bohrung 14mm, Abstand 23mm von oben, "
                    "Entfernung 31mm von links"
                ),
            }],
        },
        "aktions_klassifizierer": [{
            "phrase": (
                "oben eine Bohrung mit 14mm Durchmesser, mit einem Abstand "
                "von 23mm von der oberen Seite und einer Entfernung von 31mm "
                "von der linken Kante"
            ),
            "teil_id": "platte",
            "parent_phrase": "(keine)",
            "output": {
                "typ": "bohrung",
                "seite": "oben",
                "parameter_hints": {
                    "durchmesser": 14,
                    "abstand_oben": 23,
                    "abstand_links": 31,
                },
            },
        }],
        "normalizer_pairs": [{
            "input": {
                "beschreibung": (
                    "Bohrung 14mm, Abstand 23mm von oben, "
                    "Entfernung 31mm von links"
                ),
                "seite": "oben",
                "teil_type": "box",
                "teil_params": {"x": 120, "y": 90, "z": 18},
            },
            "output": {
                "type": "hole_single",
                "params": {"diameter": 14, "depth": None},
                "position": _pos(
                    "oben",
                    edge_distances={"top": 23, "left": 31},
                ),
                "operation": "subtract",
            },
        }],
    },
    {
        "id": "var_pocket_edge_to_edge_minimal_pair",
        "specification": (
            "90x70x20 Platte, oben eine Tasche 28x18x6, die obere Kante "
            "der Tasche 11mm von oben und die linke Seite der Tasche 17mm "
            "von links entfernt"
        ),
        "metadata": {
            "difficulty": "P2",
            "category": "variation_edge_to_edge_minimal_pair",
            "sprachstil": "technisch_ausfuehrlich",
        },
        "inventar": {
            "teil_count": 1,
            "teile": [_box_part("platte", "90x70x20 Platte", 90, 70, 20)],
            "aktionen": [{
                "teil_id": "platte",
                "seite": "oben",
                "beschreibung": (
                    "Tasche 28x18x6, obere Kante der Tasche 11mm von oben, "
                    "linke Seite der Tasche 17mm von links"
                ),
            }],
        },
        "aktions_klassifizierer": [{
            "phrase": (
                "oben eine Tasche 28x18x6, die obere Kante der Tasche "
                "11mm von oben und die linke Seite der Tasche 17mm von "
                "links entfernt"
            ),
            "teil_id": "platte",
            "parent_phrase": "(keine)",
            "output": {
                "typ": "tasche",
                "seite": "oben",
                "parameter_hints": {
                    "laenge": 28,
                    "breite": 18,
                    "tiefe": 6,
                    "kante_oben": 11,
                    "kante_links": 17,
                },
            },
        }],
        "normalizer_pairs": [{
            "input": {
                "beschreibung": (
                    "Tasche 28x18x6, obere Kante der Tasche 11mm von oben, "
                    "linke Seite der Tasche 17mm von links"
                ),
                "seite": "oben",
                "teil_type": "box",
                "teil_params": {"x": 90, "y": 70, "z": 20},
            },
            "output": {
                "type": "pocket_rect",
                "params": {"x": 28, "y": 18, "depth": 6},
                "position": _pos(
                    "oben",
                    pocket_edge_distances={"top": 11, "left": 17},
                ),
                "operation": "subtract",
            },
        }],
    },
    {
        "id": "var_center_offset_with_abstand_word",
        "specification": (
            "110mm Wuerfel, oben eine 9mm Bohrung mit einem Versatz von "
            "16mm nach rechts und 24mm nach oben"
        ),
        "metadata": {
            "difficulty": "P1",
            "category": "variation_center_offset",
            "sprachstil": "natuerlich",
        },
        "inventar": {
            "teil_count": 1,
            "teile": [_box_part("wuerfel", "110mm Wuerfel", 110, 110, 110)],
            "aktionen": [{
                "teil_id": "wuerfel",
                "seite": "oben",
                "beschreibung": (
                    "9mm Bohrung mit Versatz 16mm nach rechts und 24mm nach oben"
                ),
            }],
        },
        "aktions_klassifizierer": [{
            "phrase": (
                "oben eine 9mm Bohrung mit einem Versatz von 16mm nach "
                "rechts und 24mm nach oben"
            ),
            "teil_id": "wuerfel",
            "parent_phrase": "(keine)",
            "output": {
                "typ": "bohrung",
                "seite": "oben",
                "parameter_hints": {
                    "durchmesser": 9,
                    "versatz_rechts": 16,
                    "versatz_oben": 24,
                },
            },
        }],
        "normalizer_pairs": [{
            "input": {
                "beschreibung": (
                    "9mm Bohrung mit Versatz 16mm nach rechts und 24mm nach oben"
                ),
                "seite": "oben",
                "teil_type": "box",
                "teil_params": {"x": 110, "y": 110, "z": 110},
            },
            "output": {
                "type": "hole_single",
                "params": {"diameter": 9, "depth": None},
                "position": _pos(
                    "oben",
                    center_offset={"right": 16, "top": 24},
                    notes="von_mitte",
                ),
                "operation": "subtract",
            },
        }],
    },
    {
        "id": "var_center_offset_umgangssprachlich",
        "specification": (
            "85er Wuerfel oben ein 7er Loch, 19 nach links und 26 nach "
            "unten verschoben"
        ),
        "punctuation": {
            "raw": (
                "85er Wuerfel oben ein 7er Loch 19 nach links und 26 nach "
                "unten verschoben"
            ),
            "punctuated": (
                "85er Wuerfel, oben ein 7er Loch 19 nach links und 26 nach "
                "unten verschoben"
            ),
        },
        "metadata": {
            "difficulty": "P1",
            "category": "variation_center_offset",
            "sprachstil": "umgangssprachlich",
        },
        "inventar": {
            "teil_count": 1,
            "teile": [_box_part("wuerfel", "85mm Wuerfel", 85, 85, 85)],
            "aktionen": [{
                "teil_id": "wuerfel",
                "seite": "oben",
                "beschreibung": "7er Loch 19 nach links und 26 nach unten verschoben",
            }],
        },
        "aktions_klassifizierer": [{
            "phrase": "oben ein 7er Loch 19 nach links und 26 nach unten verschoben",
            "teil_id": "wuerfel",
            "parent_phrase": "(keine)",
            "output": {
                "typ": "bohrung",
                "seite": "oben",
                "parameter_hints": {
                    "durchmesser": 7,
                    "versatz_links": 19,
                    "versatz_unten": 26,
                },
            },
        }],
    },
]


def main() -> None:
    json.dump(TRACES, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
