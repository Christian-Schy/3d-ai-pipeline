"""
Generate curated training examples for DSPy prompt optimization.

Each example contains the CORRECT output for every agent in the chain:
  - inventar: specification → inventar dict
  - teil_definierer: (teil, aktionen, spec) → teil_definition (per part)
  - assembly: (inventar, teil_defs, spec) → full blueprint (multi-part only)
  - blueprint_architect: specification → full blueprint (monolithic BA)

Run:  python data/dspy_training/generate_examples.py
Output: data/dspy_training/examples.json
"""

import json
from pathlib import Path

EXAMPLES = []


def _pos(side="oben", alignment="centered", edge_distances=None, angle_deg=0, notes=""):
    return {"side": side, "alignment": alignment, "edge_distances": edge_distances,
            "angle_deg": angle_deg, "notes": notes}


# ══════════════════════════════════════════════════════════════════
# CORRECTED RUNS
# ══════════════════════════════════════════════════════════════════

# --- Ex 1: Run e8c756c2 (corrected) ---
EXAMPLES.append({
    "id": "wuerfel_nuten_bohrungen",
    "specification": "50mm würfel oben soll eine nut 5x5 entlang der y-achse und x-achse, rechts soll eine bohrung oben rechts ins eck jeweils 12,5mm von den kanten enternt 10mm durchmesser 10mm tief, rechts soll in würfel eine bohrung unten links hin von der linken kante 10mm entfernt von der unteren kante 5mm entfernt 10mm durchmesser 10mm tief, links soll eine nut entlang der y-achse hin und der z-achse mit 5x5 hin, unten soll eine bohrung zentral hin mit 20mm durchmesser 10mm tief",
    "inventar": {
        "teil_count": 1,
        "teile": [{"id": "wuerfel", "type": "box", "beschreibung": "50mm Wuerfel", "raw_params": {"x": 50, "y": 50, "z": 50}}],
        "aktionen": [
            {"teil_id": "wuerfel", "seite": "oben", "beschreibung": "Nut 5x5 entlang der Y-Achse"},
            {"teil_id": "wuerfel", "seite": "oben", "beschreibung": "Nut 5x5 entlang der X-Achse"},
            {"teil_id": "wuerfel", "seite": "rechts", "beschreibung": "Bohrung oben rechts im Eck 12,5mm von den Kanten entfernt 10mm Durchmesser 10mm tief"},
            {"teil_id": "wuerfel", "seite": "rechts", "beschreibung": "Bohrung unten links von der linken Kante 10mm entfernt von der unteren Kante 5mm entfernt 10mm Durchmesser 10mm tief"},
            {"teil_id": "wuerfel", "seite": "links", "beschreibung": "Nut 5x5 entlang der Y-Achse"},
            {"teil_id": "wuerfel", "seite": "links", "beschreibung": "Nut 5x5 entlang der Z-Achse"},
            {"teil_id": "wuerfel", "seite": "unten", "beschreibung": "Bohrung zentral 20mm Durchmesser 10mm tief"},
        ],
    },
    "teil_definitionen": [{
        "id": "wuerfel", "type": "box", "params": {"x": 50, "y": 50, "z": 50}, "orientation": "standard",
        "features": [
            {"id": "nut_oben_y", "type": "slot", "params": {"width": 5, "depth": 5, "length": None},
             "position": _pos("oben", notes="entlang Y"), "operation": "subtract"},
            {"id": "nut_oben_x", "type": "slot", "params": {"width": 5, "depth": 5, "length": None},
             "position": _pos("oben", notes="entlang X"), "operation": "subtract"},
            {"id": "bohrung_rechts_oben", "type": "hole_single", "params": {"diameter": 10, "depth": 10},
             "position": _pos("rechts", edge_distances={"right": 12.5, "top": 12.5}), "operation": "subtract"},
            {"id": "bohrung_rechts_unten", "type": "hole_single", "params": {"diameter": 10, "depth": 10},
             "position": _pos("rechts", edge_distances={"left": 10, "bottom": 5}), "operation": "subtract"},
            {"id": "nut_links_y", "type": "slot", "params": {"width": 5, "depth": 5, "length": None},
             "position": _pos("links", notes="entlang Y"), "operation": "subtract"},
            {"id": "nut_links_z", "type": "slot", "params": {"width": 5, "depth": 5, "length": None},
             "position": _pos("links", notes="entlang Z"), "operation": "subtract"},
            {"id": "bohrung_unten", "type": "hole_single", "params": {"diameter": 20, "depth": 10},
             "position": _pos("unten"), "operation": "subtract"},
        ],
    }],
    "blueprint": {
        "description": "50mm Wuerfel mit Nuten oben (X+Y) und links (Y+Z), Bohrungen rechts und unten",
        "build_order": ["wuerfel", "nut_oben_y", "nut_oben_x", "bohrung_rechts_oben",
                        "bohrung_rechts_unten", "nut_links_y", "nut_links_z", "bohrung_unten"],
        "features": {
            "wuerfel": {"type": "box", "params": {"x": 50, "y": 50, "z": 50}, "orientation": "standard",
                        "parent": None, "operation": "add", "notes": ""},
            "nut_oben_y": {"type": "slot", "params": {"width": 5, "depth": 5, "length": None},
                           "parent": "wuerfel", "position": _pos("oben", notes="entlang Y"), "operation": "subtract", "notes": ""},
            "nut_oben_x": {"type": "slot", "params": {"width": 5, "depth": 5, "length": None},
                           "parent": "wuerfel", "position": _pos("oben", notes="entlang X"), "operation": "subtract", "notes": ""},
            "bohrung_rechts_oben": {"type": "hole_single", "params": {"diameter": 10, "depth": 10},
                                    "parent": "wuerfel", "position": _pos("rechts", edge_distances={"right": 12.5, "top": 12.5}), "operation": "subtract", "notes": ""},
            "bohrung_rechts_unten": {"type": "hole_single", "params": {"diameter": 10, "depth": 10},
                                     "parent": "wuerfel", "position": _pos("rechts", edge_distances={"left": 10, "bottom": 5}), "operation": "subtract", "notes": ""},
            "nut_links_y": {"type": "slot", "params": {"width": 5, "depth": 5, "length": None},
                            "parent": "wuerfel", "position": _pos("links", notes="entlang Y"), "operation": "subtract", "notes": ""},
            "nut_links_z": {"type": "slot", "params": {"width": 5, "depth": 5, "length": None},
                            "parent": "wuerfel", "position": _pos("links", notes="entlang Z"), "operation": "subtract", "notes": ""},
            "bohrung_unten": {"type": "hole_single", "params": {"diameter": 20, "depth": 10},
                              "parent": "wuerfel", "position": _pos("unten"), "operation": "subtract", "notes": ""},
        },
    },
})


# --- Ex 2: Run 68ea6f64 (corrected) ---
EXAMPLES.append({
    "id": "drei_platten_lochkreis_eckbohrungen",
    "specification": "platte 100x100x20 rechts von der 1 platte soll noch eine platte mit 100x100x20 anliegen die lochkreis 60mm mit 6 bohrungen je 10mm durchmesser und durchgängig hat links von der ersten platte soll eine platte 100x100x20 hin die soll an jeder ecke eine bohrung haben die je von den kanten 20mm entfernt ist 10mm durchmesser hat und durchgängig ist",
    "inventar": {
        "teil_count": 3,
        "teile": [
            {"id": "basis", "type": "box", "beschreibung": "Grundplatte 100x100x20", "raw_params": {"x": 100, "y": 100, "z": 20}},
            {"id": "platte_rechts", "type": "box", "beschreibung": "Rechte Platte 100x100x20", "raw_params": {"x": 100, "y": 100, "z": 20}},
            {"id": "platte_links", "type": "box", "beschreibung": "Linke Platte 100x100x20", "raw_params": {"x": 100, "y": 100, "z": 20}},
        ],
        "aktionen": [
            {"teil_id": "platte_rechts", "seite": "oben", "beschreibung": "Lochkreis 60mm mit 6 Bohrungen je 10mm Durchmesser durchgaengig"},
            {"teil_id": "platte_links", "seite": "oben", "beschreibung": "4 Eckbohrungen je 20mm von den Kanten entfernt 10mm Durchmesser durchgaengig"},
        ],
    },
    "teil_definitionen": [
        {"id": "basis", "type": "box", "params": {"x": 100, "y": 100, "z": 20}, "orientation": "standard", "features": []},
        {"id": "platte_rechts", "type": "box", "params": {"x": 100, "y": 100, "z": 20}, "orientation": "standard",
         "features": [
             {"id": "lochkreis_rechts", "type": "hole_pattern_circular",
              "params": {"bolt_circle_diameter": 60, "count": 6, "hole_diameter": 10, "depth": None},
              "position": _pos("oben"), "operation": "subtract"},
         ]},
        {"id": "platte_links", "type": "box", "params": {"x": 100, "y": 100, "z": 20}, "orientation": "standard",
         "features": [
             {"id": "eckbohrungen_links", "type": "hole_pattern_grid",
              "params": {"count": 4, "inset": 20, "hole_diameter": 10, "depth": None},
              "position": _pos("oben"), "operation": "subtract"},
         ]},
    ],
    "blueprint": {
        "description": "3 Platten: Basis mit rechts anliegender Platte (Lochkreis) und links anliegender Platte (Eckbohrungen)",
        "build_order": ["basis", "platte_rechts", "lochkreis_rechts", "platte_links", "eckbohrungen_links"],
        "features": {
            "basis": {"type": "box", "params": {"x": 100, "y": 100, "z": 20}, "orientation": "standard",
                      "parent": None, "operation": "add", "notes": ""},
            "platte_rechts": {"type": "box", "params": {"x": 100, "y": 100, "z": 20}, "orientation": "standard",
                              "parent": "basis", "position": _pos("rechts"), "operation": "add", "notes": ""},
            "lochkreis_rechts": {"type": "hole_pattern_circular",
                                 "params": {"bolt_circle_diameter": 60, "count": 6, "hole_diameter": 10, "depth": None},
                                 "parent": "platte_rechts", "position": _pos("oben"), "operation": "subtract", "notes": ""},
            "platte_links": {"type": "box", "params": {"x": 100, "y": 100, "z": 20}, "orientation": "standard",
                             "parent": "basis", "position": _pos("links"), "operation": "add", "notes": ""},
            "eckbohrungen_links": {"type": "hole_pattern_grid",
                                   "params": {"count": 4, "inset": 20, "hole_diameter": 10, "depth": None},
                                   "parent": "platte_links", "position": _pos("oben"), "operation": "subtract", "notes": ""},
        },
    },
})


# --- Ex 3: Run c696d68f (corrected) ---
EXAMPLES.append({
    "id": "platte_zwei_bohrungsreihen",
    "specification": "100x100x20 platte oben soll entlang der x-achse 5 bohrungen positioniert werden mit 10mm abstand dazwischen zentral mit 5mm bohrungen durchgängig, oben sollen auch auf der y-achse 5 bohrungen hin je 10mm entfernt mit 5mm durchmesser und durchgängig",
    "inventar": {
        "teil_count": 1,
        "teile": [{"id": "platte", "type": "box", "beschreibung": "Platte 100x100x20", "raw_params": {"x": 100, "y": 100, "z": 20}}],
        "aktionen": [
            {"teil_id": "platte", "seite": "oben", "beschreibung": "5 Bohrungen entlang der X-Achse mit 10mm Abstand zentral 5mm Durchmesser durchgaengig"},
            {"teil_id": "platte", "seite": "oben", "beschreibung": "5 Bohrungen entlang der Y-Achse mit 10mm Abstand 5mm Durchmesser durchgaengig"},
        ],
    },
    "teil_definitionen": [{
        "id": "platte", "type": "box", "params": {"x": 100, "y": 100, "z": 20}, "orientation": "standard",
        "features": [
            {"id": "bohrungen_x", "type": "hole_pattern_linear",
             "params": {"count": 5, "spacing": 10, "start_offset": 30, "hole_diameter": 5, "depth": None},
             "position": _pos("oben", notes="entlang X"), "operation": "subtract"},
            {"id": "bohrungen_y", "type": "hole_pattern_linear",
             "params": {"count": 5, "spacing": 10, "start_offset": 30, "hole_diameter": 5, "depth": None},
             "position": _pos("oben", notes="entlang Y"), "operation": "subtract"},
        ],
    }],
    "blueprint": {
        "description": "Platte 100x100x20 mit zwei Bohrungsreihen oben (entlang X und Y)",
        "build_order": ["platte", "bohrungen_x", "bohrungen_y"],
        "features": {
            "platte": {"type": "box", "params": {"x": 100, "y": 100, "z": 20}, "orientation": "standard",
                       "parent": None, "operation": "add", "notes": ""},
            "bohrungen_x": {"type": "hole_pattern_linear",
                            "params": {"count": 5, "spacing": 10, "start_offset": 30, "hole_diameter": 5, "depth": None},
                            "parent": "platte", "position": _pos("oben", notes="entlang X"), "operation": "subtract", "notes": ""},
            "bohrungen_y": {"type": "hole_pattern_linear",
                            "params": {"count": 5, "spacing": 10, "start_offset": 30, "hole_diameter": 5, "depth": None},
                            "parent": "platte", "position": _pos("oben", notes="entlang Y"), "operation": "subtract", "notes": ""},
        },
    },
})


# ══════════════════════════════════════════════════════════════════
# USER EXAMPLES (bsp 1-4)
# ══════════════════════════════════════════════════════════════════

# --- Ex 4: bsp1 ---
EXAMPLES.append({
    "id": "bsp1_drei_platten_lochkreis_bohrungsreihe",
    "specification": "platte 200x200x20 rechts an der seite liegt eine platte an mit 100x100x20 und lochkreis 70mm mit 8 bohrungen je 12mm und durchgängig auf die erste platte kommt oben auf die hintere seite eine platte 50x100x20 hin hochkant die 50mm liegen an der kante hinten bündig an da auf die 50x100 fläche sollen entlang der y-achse 5 löcher der reihe nach hin mit 10mm abstand jeweils und 5mm durchmesser und 10mm tief",
    "inventar": {
        "teil_count": 3,
        "teile": [
            {"id": "basis", "type": "box", "beschreibung": "Grundplatte 200x200x20", "raw_params": {"x": 200, "y": 200, "z": 20}},
            {"id": "platte_rechts", "type": "box", "beschreibung": "Rechte Platte 100x100x20", "raw_params": {"x": 100, "y": 100, "z": 20}},
            {"id": "platte_hinten", "type": "box", "beschreibung": "Hintere Platte 50x100x20 hochkant", "raw_params": {"x": 50, "y": 100, "z": 20}},
        ],
        "aktionen": [
            {"teil_id": "platte_rechts", "seite": "oben", "beschreibung": "Lochkreis 70mm mit 8 Bohrungen je 12mm Durchmesser durchgaengig"},
            {"teil_id": "platte_hinten", "seite": "oben", "beschreibung": "5 Bohrungen der Reihe nach entlang Y-Achse mit 10mm Abstand 5mm Durchmesser 10mm tief"},
        ],
    },
    "teil_definitionen": [
        {"id": "basis", "type": "box", "params": {"x": 200, "y": 200, "z": 20}, "orientation": "standard", "features": []},
        {"id": "platte_rechts", "type": "box", "params": {"x": 100, "y": 100, "z": 20}, "orientation": "standard",
         "features": [
             {"id": "lochkreis_rechts", "type": "hole_pattern_circular",
              "params": {"bolt_circle_diameter": 70, "count": 8, "hole_diameter": 12, "depth": None},
              "position": _pos("oben"), "operation": "subtract"},
         ]},
        {"id": "platte_hinten", "type": "box", "params": {"x": 50, "y": 100, "z": 20}, "orientation": "hochkant",
         "features": [
             {"id": "bohrungen_hinten", "type": "hole_pattern_linear",
              "params": {"count": 5, "spacing": 10, "start_offset": 30, "hole_diameter": 5, "depth": 10},
              "position": _pos("oben", notes="entlang Y"), "operation": "subtract"},
         ]},
    ],
    "blueprint": {
        "description": "Grundplatte 200x200x20 mit rechts anliegender Platte (Lochkreis) und hinten hochkanter Platte (Bohrungsreihe)",
        "build_order": ["basis", "platte_rechts", "lochkreis_rechts", "platte_hinten", "bohrungen_hinten"],
        "features": {
            "basis": {"type": "box", "params": {"x": 200, "y": 200, "z": 20}, "orientation": "standard",
                      "parent": None, "operation": "add", "notes": ""},
            "platte_rechts": {"type": "box", "params": {"x": 100, "y": 100, "z": 20}, "orientation": "standard",
                              "parent": "basis", "position": _pos("rechts"), "operation": "add", "notes": ""},
            "lochkreis_rechts": {"type": "hole_pattern_circular",
                                 "params": {"bolt_circle_diameter": 70, "count": 8, "hole_diameter": 12, "depth": None},
                                 "parent": "platte_rechts", "position": _pos("oben"), "operation": "subtract", "notes": ""},
            "platte_hinten": {"type": "box", "params": {"x": 50, "y": 100, "z": 20}, "orientation": "hochkant",
                              "parent": "basis", "position": _pos("oben", "flush_top"), "operation": "add", "notes": ""},
            "bohrungen_hinten": {"type": "hole_pattern_linear",
                                 "params": {"count": 5, "spacing": 10, "start_offset": 30, "hole_diameter": 5, "depth": 10},
                                 "parent": "platte_hinten", "position": _pos("oben", notes="entlang Y"), "operation": "subtract", "notes": ""},
        },
    },
})


# --- Ex 5: bsp2 ---
EXAMPLES.append({
    "id": "bsp2_platte_vier_zylinder_bohrungen",
    "specification": "platte mit 100x100x20 an jede ecke soll ein zylinder hin von den kanten entfernt 10mm jeweils mit 20mm durchmesser und 50mm höhe in den zylinder hinten rechts und vorne links soll von oben eine bohrung hin mit 10mm durchmesser und 25mm tiefe",
    "inventar": {
        "teil_count": 5,
        "teile": [
            {"id": "basis", "type": "box", "beschreibung": "Platte 100x100x20", "raw_params": {"x": 100, "y": 100, "z": 20}},
            {"id": "zylinder_vl", "type": "cylinder", "beschreibung": "Zylinder vorne links", "raw_params": {"diameter": 20, "height": 50}},
            {"id": "zylinder_vr", "type": "cylinder", "beschreibung": "Zylinder vorne rechts", "raw_params": {"diameter": 20, "height": 50}},
            {"id": "zylinder_hl", "type": "cylinder", "beschreibung": "Zylinder hinten links", "raw_params": {"diameter": 20, "height": 50}},
            {"id": "zylinder_hr", "type": "cylinder", "beschreibung": "Zylinder hinten rechts", "raw_params": {"diameter": 20, "height": 50}},
        ],
        "aktionen": [
            {"teil_id": "zylinder_hr", "seite": "oben", "beschreibung": "Bohrung von oben 10mm Durchmesser 25mm tief"},
            {"teil_id": "zylinder_vl", "seite": "oben", "beschreibung": "Bohrung von oben 10mm Durchmesser 25mm tief"},
        ],
    },
    "teil_definitionen": [
        {"id": "basis", "type": "box", "params": {"x": 100, "y": 100, "z": 20}, "orientation": "standard", "features": []},
        {"id": "zylinder_vl", "type": "cylinder", "params": {"diameter": 20, "height": 50}, "orientation": "standard",
         "features": [
             {"id": "bohrung_vl", "type": "hole_single", "params": {"diameter": 10, "depth": 25},
              "position": _pos("oben"), "operation": "subtract"},
         ]},
        {"id": "zylinder_vr", "type": "cylinder", "params": {"diameter": 20, "height": 50}, "orientation": "standard", "features": []},
        {"id": "zylinder_hl", "type": "cylinder", "params": {"diameter": 20, "height": 50}, "orientation": "standard", "features": []},
        {"id": "zylinder_hr", "type": "cylinder", "params": {"diameter": 20, "height": 50}, "orientation": "standard",
         "features": [
             {"id": "bohrung_hr", "type": "hole_single", "params": {"diameter": 10, "depth": 25},
              "position": _pos("oben"), "operation": "subtract"},
         ]},
    ],
    "blueprint": {
        "description": "Platte 100x100x20 mit 4 Zylindern an den Ecken, Bohrungen in Zylinder hinten-rechts und vorne-links",
        "build_order": ["basis", "zylinder_vl", "bohrung_vl", "zylinder_vr", "zylinder_hl", "zylinder_hr", "bohrung_hr"],
        "features": {
            "basis": {"type": "box", "params": {"x": 100, "y": 100, "z": 20}, "orientation": "standard",
                      "parent": None, "operation": "add", "notes": ""},
            "zylinder_vl": {"type": "cylinder", "params": {"diameter": 20, "height": 50}, "orientation": "standard",
                            "parent": "basis", "position": _pos("oben", edge_distances={"left": 10, "bottom": 10}), "operation": "add", "notes": ""},
            "bohrung_vl": {"type": "hole_single", "params": {"diameter": 10, "depth": 25},
                           "parent": "zylinder_vl", "position": _pos("oben"), "operation": "subtract", "notes": ""},
            "zylinder_vr": {"type": "cylinder", "params": {"diameter": 20, "height": 50}, "orientation": "standard",
                            "parent": "basis", "position": _pos("oben", edge_distances={"right": 10, "bottom": 10}), "operation": "add", "notes": ""},
            "zylinder_hl": {"type": "cylinder", "params": {"diameter": 20, "height": 50}, "orientation": "standard",
                            "parent": "basis", "position": _pos("oben", edge_distances={"left": 10, "top": 10}), "operation": "add", "notes": ""},
            "zylinder_hr": {"type": "cylinder", "params": {"diameter": 20, "height": 50}, "orientation": "standard",
                            "parent": "basis", "position": _pos("oben", edge_distances={"right": 10, "top": 10}), "operation": "add", "notes": ""},
            "bohrung_hr": {"type": "hole_single", "params": {"diameter": 10, "depth": 25},
                           "parent": "zylinder_hr", "position": _pos("oben"), "operation": "subtract", "notes": ""},
        },
    },
})


# --- Ex 6: bsp3 ---
EXAMPLES.append({
    "id": "bsp3_drei_platten_zylinder",
    "specification": "eine platte 200x200x20 auf die soll eine platte hin mit 100x100x20 auf die rechte seite hochkant und die lange seite liegt bündig zur kante auf die linke seite soll eine 80x80x20 platte hin von der linken seite 20mm entfernt die lange seite parallel zur außenkante und hochkant auf dieser 3. platte soll ein zylinder zentral hin mit 20mm durchmesser und 20mm länge der zylinder soll nach außen gehen",
    "inventar": {
        "teil_count": 4,
        "teile": [
            {"id": "basis", "type": "box", "beschreibung": "Grundplatte 200x200x20", "raw_params": {"x": 200, "y": 200, "z": 20}},
            {"id": "platte_rechts", "type": "box", "beschreibung": "Rechte Platte 100x100x20 hochkant", "raw_params": {"x": 100, "y": 100, "z": 20}},
            {"id": "platte_links", "type": "box", "beschreibung": "Linke Platte 80x80x20 hochkant", "raw_params": {"x": 80, "y": 80, "z": 20}},
            {"id": "zylinder_links", "type": "cylinder", "beschreibung": "Zylinder auf linker Platte zentral 20mm Durchmesser 20mm lang nach aussen", "raw_params": {"diameter": 20, "height": 20}},
        ],
        "aktionen": [],
    },
    "teil_definitionen": [
        {"id": "basis", "type": "box", "params": {"x": 200, "y": 200, "z": 20}, "orientation": "standard", "features": []},
        {"id": "platte_rechts", "type": "box", "params": {"x": 100, "y": 100, "z": 20}, "orientation": "hochkant", "features": []},
        {"id": "platte_links", "type": "box", "params": {"x": 80, "y": 80, "z": 20}, "orientation": "hochkant", "features": []},
        {"id": "zylinder_links", "type": "cylinder", "params": {"diameter": 20, "height": 20}, "orientation": "standard", "features": []},
    ],
    "blueprint": {
        "description": "Grundplatte 200x200x20 mit rechts hochkanter Platte, links versetzter Platte mit Zylinder nach aussen",
        "build_order": ["basis", "platte_rechts", "platte_links", "zylinder_links"],
        "features": {
            "basis": {"type": "box", "params": {"x": 200, "y": 200, "z": 20}, "orientation": "standard",
                      "parent": None, "operation": "add", "notes": ""},
            "platte_rechts": {"type": "box", "params": {"x": 100, "y": 100, "z": 20}, "orientation": "hochkant",
                              "parent": "basis", "position": _pos("rechts", "flush_right"), "operation": "add", "notes": ""},
            "platte_links": {"type": "box", "params": {"x": 80, "y": 80, "z": 20}, "orientation": "hochkant",
                             "parent": "basis", "position": _pos("links", edge_distances={"left": 20}), "operation": "add", "notes": ""},
            "zylinder_links": {"type": "cylinder", "params": {"diameter": 20, "height": 20}, "orientation": "standard",
                               "parent": "platte_links", "position": _pos("links"), "operation": "add",
                               "notes": "nach aussen zeigend"},
        },
    },
})


# --- Ex 7: bsp4 ---
EXAMPLES.append({
    "id": "bsp4_platte_zwei_seitenplatten_zylinder",
    "specification": "platte mit 140x100x20 links und rechts sollen von den kanten jeweils platten hin mit 180x180x20 hochkant und die lange seite jeweils parallel zur kante auf die rechte platte kommt ein zylinder an die obere linke ecke von der oberen kante 10mm entfernt von der linken kante 20mm entfernt mit durchmesser 20mm und 60mm lang dieser zylinder soll dann nach innen zeigen",
    "inventar": {
        "teil_count": 4,
        "teile": [
            {"id": "basis", "type": "box", "beschreibung": "Grundplatte 140x100x20", "raw_params": {"x": 140, "y": 100, "z": 20}},
            {"id": "platte_rechts", "type": "box", "beschreibung": "Rechte Platte 180x180x20 hochkant", "raw_params": {"x": 180, "y": 180, "z": 20}},
            {"id": "platte_links", "type": "box", "beschreibung": "Linke Platte 180x180x20 hochkant", "raw_params": {"x": 180, "y": 180, "z": 20}},
            {"id": "zylinder_rechts", "type": "cylinder", "beschreibung": "Zylinder auf rechter Platte oben links 20mm Durchmesser 60mm lang nach innen", "raw_params": {"diameter": 20, "height": 60}},
        ],
        "aktionen": [],
    },
    "teil_definitionen": [
        {"id": "basis", "type": "box", "params": {"x": 140, "y": 100, "z": 20}, "orientation": "standard", "features": []},
        {"id": "platte_rechts", "type": "box", "params": {"x": 180, "y": 180, "z": 20}, "orientation": "hochkant", "features": []},
        {"id": "platte_links", "type": "box", "params": {"x": 180, "y": 180, "z": 20}, "orientation": "hochkant", "features": []},
        {"id": "zylinder_rechts", "type": "cylinder", "params": {"diameter": 20, "height": 60}, "orientation": "standard", "features": []},
    ],
    "blueprint": {
        "description": "Grundplatte 140x100x20 mit links und rechts hochkanten Platten, Zylinder auf rechter Platte nach innen",
        "build_order": ["basis", "platte_rechts", "platte_links", "zylinder_rechts"],
        "features": {
            "basis": {"type": "box", "params": {"x": 140, "y": 100, "z": 20}, "orientation": "standard",
                      "parent": None, "operation": "add", "notes": ""},
            "platte_rechts": {"type": "box", "params": {"x": 180, "y": 180, "z": 20}, "orientation": "hochkant",
                              "parent": "basis", "position": _pos("rechts"), "operation": "add", "notes": ""},
            "platte_links": {"type": "box", "params": {"x": 180, "y": 180, "z": 20}, "orientation": "hochkant",
                             "parent": "basis", "position": _pos("links"), "operation": "add", "notes": ""},
            "zylinder_rechts": {"type": "cylinder", "params": {"diameter": 20, "height": 60}, "orientation": "standard",
                                "parent": "platte_rechts",
                                "position": _pos("rechts", edge_distances={"top": 10, "left": 20}),
                                "operation": "add", "notes": "nach innen zeigend"},
        },
    },
})


# ══════════════════════════════════════════════════════════════════
# ADDITIONAL EXAMPLES (to reach ~20)
# ══════════════════════════════════════════════════════════════════

# --- Ex 8: Einfacher Wuerfel mit Bohrung ---
EXAMPLES.append({
    "id": "einfacher_wuerfel_bohrung",
    "specification": "30mm wuerfel mit einer bohrung oben zentral 8mm durchmesser durchgängig",
    "inventar": {
        "teil_count": 1,
        "teile": [{"id": "wuerfel", "type": "box", "beschreibung": "30mm Wuerfel", "raw_params": {"x": 30, "y": 30, "z": 30}}],
        "aktionen": [{"teil_id": "wuerfel", "seite": "oben", "beschreibung": "Bohrung zentral 8mm Durchmesser durchgaengig"}],
    },
    "teil_definitionen": [{
        "id": "wuerfel", "type": "box", "params": {"x": 30, "y": 30, "z": 30}, "orientation": "standard",
        "features": [
            {"id": "bohrung_oben", "type": "hole_single", "params": {"diameter": 8, "depth": None},
             "position": _pos("oben"), "operation": "subtract"},
        ],
    }],
    "blueprint": {
        "description": "30mm Wuerfel mit zentraler Durchgangsbohrung oben",
        "build_order": ["wuerfel", "bohrung_oben"],
        "features": {
            "wuerfel": {"type": "box", "params": {"x": 30, "y": 30, "z": 30}, "orientation": "standard",
                        "parent": None, "operation": "add", "notes": ""},
            "bohrung_oben": {"type": "hole_single", "params": {"diameter": 8, "depth": None},
                             "parent": "wuerfel", "position": _pos("oben"), "operation": "subtract", "notes": ""},
        },
    },
})


# --- Ex 9: Platte mit Tasche und Fase ---
EXAMPLES.append({
    "id": "platte_tasche_fase",
    "specification": "platte 80x60x15 oben mittig eine rechteckige tasche 40x30 mit 8mm tiefe und 2mm fase an allen oberen kanten",
    "inventar": {
        "teil_count": 1,
        "teile": [{"id": "platte", "type": "box", "beschreibung": "Platte 80x60x15", "raw_params": {"x": 80, "y": 60, "z": 15}}],
        "aktionen": [
            {"teil_id": "platte", "seite": "oben", "beschreibung": "Rechteckige Tasche 40x30 mit 8mm Tiefe zentral"},
            {"teil_id": "platte", "seite": "oben", "beschreibung": "Fase 2mm an allen oberen Kanten"},
        ],
    },
    "teil_definitionen": [{
        "id": "platte", "type": "box", "params": {"x": 80, "y": 60, "z": 15}, "orientation": "standard",
        "features": [
            {"id": "tasche_oben", "type": "pocket_rect", "params": {"x": 40, "y": 30, "depth": 8},
             "position": _pos("oben"), "operation": "subtract"},
            {"id": "fase_oben", "type": "chamfer", "params": {"size": 2},
             "position": _pos("oben"), "operation": "modify"},
        ],
    }],
    "blueprint": {
        "description": "Platte 80x60x15 mit zentraler Tasche und Fase an oberen Kanten",
        "build_order": ["platte", "tasche_oben", "fase_oben"],
        "features": {
            "platte": {"type": "box", "params": {"x": 80, "y": 60, "z": 15}, "orientation": "standard",
                       "parent": None, "operation": "add", "notes": ""},
            "tasche_oben": {"type": "pocket_rect", "params": {"x": 40, "y": 30, "depth": 8},
                            "parent": "platte", "position": _pos("oben"), "operation": "subtract", "notes": ""},
            "fase_oben": {"type": "chamfer", "params": {"size": 2},
                          "parent": "platte", "position": _pos("oben"), "operation": "modify", "notes": ""},
        },
    },
})


# --- Ex 10: Zylinder mit Durchgangsbohrung ---
EXAMPLES.append({
    "id": "zylinder_durchgangsbohrung",
    "specification": "zylinder 40mm durchmesser 60mm hoch mit einer durchgangsbohrung zentral von oben 15mm durchmesser",
    "inventar": {
        "teil_count": 1,
        "teile": [{"id": "zylinder", "type": "cylinder", "beschreibung": "Zylinder 40mm Durchmesser 60mm hoch", "raw_params": {"diameter": 40, "height": 60}}],
        "aktionen": [{"teil_id": "zylinder", "seite": "oben", "beschreibung": "Durchgangsbohrung zentral 15mm Durchmesser"}],
    },
    "teil_definitionen": [{
        "id": "zylinder", "type": "cylinder", "params": {"diameter": 40, "height": 60}, "orientation": "standard",
        "features": [
            {"id": "bohrung_zentral", "type": "hole_single", "params": {"diameter": 15, "depth": None},
             "position": _pos("oben"), "operation": "subtract"},
        ],
    }],
    "blueprint": {
        "description": "Zylinder 40x60mm mit zentraler Durchgangsbohrung",
        "build_order": ["zylinder", "bohrung_zentral"],
        "features": {
            "zylinder": {"type": "cylinder", "params": {"diameter": 40, "height": 60}, "orientation": "standard",
                         "parent": None, "operation": "add", "notes": ""},
            "bohrung_zentral": {"type": "hole_single", "params": {"diameter": 15, "depth": None},
                                "parent": "zylinder", "position": _pos("oben"), "operation": "subtract", "notes": ""},
        },
    },
})


# --- Ex 11: Box mit Nut und Rundung ---
EXAMPLES.append({
    "id": "box_nut_rundung",
    "specification": "box 60x40x25 oben eine nut 4mm breit 3mm tief entlang der x-achse und 1mm rundung an allen oberen kanten",
    "inventar": {
        "teil_count": 1,
        "teile": [{"id": "box", "type": "box", "beschreibung": "Box 60x40x25", "raw_params": {"x": 60, "y": 40, "z": 25}}],
        "aktionen": [
            {"teil_id": "box", "seite": "oben", "beschreibung": "Nut 4mm breit 3mm tief entlang der X-Achse"},
            {"teil_id": "box", "seite": "oben", "beschreibung": "Rundung 1mm an allen oberen Kanten"},
        ],
    },
    "teil_definitionen": [{
        "id": "box", "type": "box", "params": {"x": 60, "y": 40, "z": 25}, "orientation": "standard",
        "features": [
            {"id": "nut_oben", "type": "slot", "params": {"width": 4, "depth": 3, "length": None},
             "position": _pos("oben", notes="entlang X"), "operation": "subtract"},
            {"id": "rundung_oben", "type": "fillet", "params": {"radius": 1},
             "position": _pos("oben"), "operation": "modify"},
        ],
    }],
    "blueprint": {
        "description": "Box 60x40x25 mit Nut entlang X und Rundung an oberen Kanten",
        "build_order": ["box", "nut_oben", "rundung_oben"],
        "features": {
            "box": {"type": "box", "params": {"x": 60, "y": 40, "z": 25}, "orientation": "standard",
                    "parent": None, "operation": "add", "notes": ""},
            "nut_oben": {"type": "slot", "params": {"width": 4, "depth": 3, "length": None},
                         "parent": "box", "position": _pos("oben", notes="entlang X"), "operation": "subtract", "notes": ""},
            "rundung_oben": {"type": "fillet", "params": {"radius": 1},
                             "parent": "box", "position": _pos("oben"), "operation": "modify", "notes": ""},
        },
    },
})


# --- Ex 12: Platte mit Lochkreis ---
EXAMPLES.append({
    "id": "platte_lochkreis",
    "specification": "platte 120x120x10 mit einem lochkreis oben zentral 80mm durchmesser 12 bohrungen je 6mm durchmesser und durchgängig",
    "inventar": {
        "teil_count": 1,
        "teile": [{"id": "platte", "type": "box", "beschreibung": "Platte 120x120x10", "raw_params": {"x": 120, "y": 120, "z": 10}}],
        "aktionen": [{"teil_id": "platte", "seite": "oben", "beschreibung": "Lochkreis 80mm mit 12 Bohrungen je 6mm Durchmesser durchgaengig"}],
    },
    "teil_definitionen": [{
        "id": "platte", "type": "box", "params": {"x": 120, "y": 120, "z": 10}, "orientation": "standard",
        "features": [
            {"id": "lochkreis_oben", "type": "hole_pattern_circular",
             "params": {"bolt_circle_diameter": 80, "count": 12, "hole_diameter": 6, "depth": None},
             "position": _pos("oben"), "operation": "subtract"},
        ],
    }],
    "blueprint": {
        "description": "Platte 120x120x10 mit zentralem Lochkreis",
        "build_order": ["platte", "lochkreis_oben"],
        "features": {
            "platte": {"type": "box", "params": {"x": 120, "y": 120, "z": 10}, "orientation": "standard",
                       "parent": None, "operation": "add", "notes": ""},
            "lochkreis_oben": {"type": "hole_pattern_circular",
                               "params": {"bolt_circle_diameter": 80, "count": 12, "hole_diameter": 6, "depth": None},
                               "parent": "platte", "position": _pos("oben"), "operation": "subtract", "notes": ""},
        },
    },
})


# --- Ex 13: Platte mit Eckbohrungen ---
EXAMPLES.append({
    "id": "platte_eckbohrungen",
    "specification": "platte 150x100x12 oben sollen 4 eckbohrungen hin jeweils 15mm von den kanten entfernt 8mm durchmesser und durchgängig",
    "inventar": {
        "teil_count": 1,
        "teile": [{"id": "platte", "type": "box", "beschreibung": "Platte 150x100x12", "raw_params": {"x": 150, "y": 100, "z": 12}}],
        "aktionen": [{"teil_id": "platte", "seite": "oben", "beschreibung": "4 Eckbohrungen je 15mm von den Kanten entfernt 8mm Durchmesser durchgaengig"}],
    },
    "teil_definitionen": [{
        "id": "platte", "type": "box", "params": {"x": 150, "y": 100, "z": 12}, "orientation": "standard",
        "features": [
            {"id": "eckbohrungen", "type": "hole_pattern_grid",
             "params": {"count": 4, "inset": 15, "hole_diameter": 8, "depth": None},
             "position": _pos("oben"), "operation": "subtract"},
        ],
    }],
    "blueprint": {
        "description": "Platte 150x100x12 mit 4 Eckbohrungen",
        "build_order": ["platte", "eckbohrungen"],
        "features": {
            "platte": {"type": "box", "params": {"x": 150, "y": 100, "z": 12}, "orientation": "standard",
                       "parent": None, "operation": "add", "notes": ""},
            "eckbohrungen": {"type": "hole_pattern_grid",
                             "params": {"count": 4, "inset": 15, "hole_diameter": 8, "depth": None},
                             "parent": "platte", "position": _pos("oben"), "operation": "subtract", "notes": ""},
        },
    },
})


# --- Ex 14: Box mit Shell (Aushoelung) ---
EXAMPLES.append({
    "id": "box_shell",
    "specification": "box 50x50x40 ausgehöhlt mit 3mm wandstärke offen nach oben",
    "inventar": {
        "teil_count": 1,
        "teile": [{"id": "box", "type": "box", "beschreibung": "Box 50x50x40", "raw_params": {"x": 50, "y": 50, "z": 40}}],
        "aktionen": [{"teil_id": "box", "seite": "oben", "beschreibung": "Aushöhlung 3mm Wandstärke offen nach oben"}],
    },
    "teil_definitionen": [{
        "id": "box", "type": "box", "params": {"x": 50, "y": 50, "z": 40}, "orientation": "standard",
        "features": [
            {"id": "shell_oben", "type": "shell", "params": {"thickness": 3},
             "position": _pos("oben"), "operation": "modify"},
        ],
    }],
    "blueprint": {
        "description": "Box 50x50x40 ausgehöhlt mit 3mm Wandstärke",
        "build_order": ["box", "shell_oben"],
        "features": {
            "box": {"type": "box", "params": {"x": 50, "y": 50, "z": 40}, "orientation": "standard",
                    "parent": None, "operation": "add", "notes": ""},
            "shell_oben": {"type": "shell", "params": {"thickness": 3},
                           "parent": "box", "position": _pos("oben"), "operation": "modify", "notes": ""},
        },
    },
})


# --- Ex 15: Zwei Platten T-Form ---
EXAMPLES.append({
    "id": "t_form_zwei_platten",
    "specification": "platte 200x100x20 auf die oberseite mittig eine platte 100x100x20 hochkant die lange seite parallel zur y-achse",
    "inventar": {
        "teil_count": 2,
        "teile": [
            {"id": "basis", "type": "box", "beschreibung": "Grundplatte 200x100x20", "raw_params": {"x": 200, "y": 100, "z": 20}},
            {"id": "steg", "type": "box", "beschreibung": "Stegplatte 100x100x20 hochkant", "raw_params": {"x": 100, "y": 100, "z": 20}},
        ],
        "aktionen": [],
    },
    "teil_definitionen": [
        {"id": "basis", "type": "box", "params": {"x": 200, "y": 100, "z": 20}, "orientation": "standard", "features": []},
        {"id": "steg", "type": "box", "params": {"x": 100, "y": 100, "z": 20}, "orientation": "hochkant", "features": []},
    ],
    "blueprint": {
        "description": "T-Form: Grundplatte 200x100x20 mit mittig aufgesetzter Platte hochkant",
        "build_order": ["basis", "steg"],
        "features": {
            "basis": {"type": "box", "params": {"x": 200, "y": 100, "z": 20}, "orientation": "standard",
                      "parent": None, "operation": "add", "notes": ""},
            "steg": {"type": "box", "params": {"x": 100, "y": 100, "z": 20}, "orientation": "hochkant",
                     "parent": "basis", "position": _pos("oben"), "operation": "add", "notes": ""},
        },
    },
})


# --- Ex 16: Platte mit 2 Nuten kreuzfoermig ---
EXAMPLES.append({
    "id": "platte_kreuz_nuten",
    "specification": "platte 100x100x20 oben eine nut 6mm breit 4mm tief entlang x und eine nut 6mm breit 4mm tief entlang y beide zentral",
    "inventar": {
        "teil_count": 1,
        "teile": [{"id": "platte", "type": "box", "beschreibung": "Platte 100x100x20", "raw_params": {"x": 100, "y": 100, "z": 20}}],
        "aktionen": [
            {"teil_id": "platte", "seite": "oben", "beschreibung": "Nut 6mm breit 4mm tief entlang X zentral"},
            {"teil_id": "platte", "seite": "oben", "beschreibung": "Nut 6mm breit 4mm tief entlang Y zentral"},
        ],
    },
    "teil_definitionen": [{
        "id": "platte", "type": "box", "params": {"x": 100, "y": 100, "z": 20}, "orientation": "standard",
        "features": [
            {"id": "nut_x", "type": "slot", "params": {"width": 6, "depth": 4, "length": None},
             "position": _pos("oben", notes="entlang X"), "operation": "subtract"},
            {"id": "nut_y", "type": "slot", "params": {"width": 6, "depth": 4, "length": None},
             "position": _pos("oben", notes="entlang Y"), "operation": "subtract"},
        ],
    }],
    "blueprint": {
        "description": "Platte 100x100x20 mit kreuzförmigen Nuten oben",
        "build_order": ["platte", "nut_x", "nut_y"],
        "features": {
            "platte": {"type": "box", "params": {"x": 100, "y": 100, "z": 20}, "orientation": "standard",
                       "parent": None, "operation": "add", "notes": ""},
            "nut_x": {"type": "slot", "params": {"width": 6, "depth": 4, "length": None},
                      "parent": "platte", "position": _pos("oben", notes="entlang X"), "operation": "subtract", "notes": ""},
            "nut_y": {"type": "slot", "params": {"width": 6, "depth": 4, "length": None},
                      "parent": "platte", "position": _pos("oben", notes="entlang Y"), "operation": "subtract", "notes": ""},
        },
    },
})


# --- Ex 17: Box mit Bohrungen auf 3 Seiten ---
EXAMPLES.append({
    "id": "box_bohrungen_drei_seiten",
    "specification": "box 40x40x40 oben eine bohrung zentral 10mm durchgängig rechts eine bohrung zentral 8mm 15mm tief vorne eine bohrung zentral 8mm 15mm tief",
    "inventar": {
        "teil_count": 1,
        "teile": [{"id": "box", "type": "box", "beschreibung": "Box 40x40x40", "raw_params": {"x": 40, "y": 40, "z": 40}}],
        "aktionen": [
            {"teil_id": "box", "seite": "oben", "beschreibung": "Bohrung zentral 10mm Durchmesser durchgaengig"},
            {"teil_id": "box", "seite": "rechts", "beschreibung": "Bohrung zentral 8mm Durchmesser 15mm tief"},
            {"teil_id": "box", "seite": "vorne", "beschreibung": "Bohrung zentral 8mm Durchmesser 15mm tief"},
        ],
    },
    "teil_definitionen": [{
        "id": "box", "type": "box", "params": {"x": 40, "y": 40, "z": 40}, "orientation": "standard",
        "features": [
            {"id": "bohrung_oben", "type": "hole_single", "params": {"diameter": 10, "depth": None},
             "position": _pos("oben"), "operation": "subtract"},
            {"id": "bohrung_rechts", "type": "hole_single", "params": {"diameter": 8, "depth": 15},
             "position": _pos("rechts"), "operation": "subtract"},
            {"id": "bohrung_vorne", "type": "hole_single", "params": {"diameter": 8, "depth": 15},
             "position": _pos("vorne"), "operation": "subtract"},
        ],
    }],
    "blueprint": {
        "description": "Box 40x40x40 mit Bohrungen auf oben, rechts und vorne",
        "build_order": ["box", "bohrung_oben", "bohrung_rechts", "bohrung_vorne"],
        "features": {
            "box": {"type": "box", "params": {"x": 40, "y": 40, "z": 40}, "orientation": "standard",
                    "parent": None, "operation": "add", "notes": ""},
            "bohrung_oben": {"type": "hole_single", "params": {"diameter": 10, "depth": None},
                             "parent": "box", "position": _pos("oben"), "operation": "subtract", "notes": ""},
            "bohrung_rechts": {"type": "hole_single", "params": {"diameter": 8, "depth": 15},
                               "parent": "box", "position": _pos("rechts"), "operation": "subtract", "notes": ""},
            "bohrung_vorne": {"type": "hole_single", "params": {"diameter": 8, "depth": 15},
                              "parent": "box", "position": _pos("vorne"), "operation": "subtract", "notes": ""},
        },
    },
})


# --- Ex 18: Platte mit Nut und Bohrungsreihe ---
EXAMPLES.append({
    "id": "platte_nut_bohrungsreihe",
    "specification": "platte 160x80x15 oben eine nut 5mm breit 3mm tief entlang y und daneben rechts von der nut 20mm entfernt 4 bohrungen in einer reihe entlang y mit 15mm abstand 6mm durchmesser und 10mm tief",
    "inventar": {
        "teil_count": 1,
        "teile": [{"id": "platte", "type": "box", "beschreibung": "Platte 160x80x15", "raw_params": {"x": 160, "y": 80, "z": 15}}],
        "aktionen": [
            {"teil_id": "platte", "seite": "oben", "beschreibung": "Nut 5mm breit 3mm tief entlang Y zentral"},
            {"teil_id": "platte", "seite": "oben", "beschreibung": "4 Bohrungen in Reihe entlang Y rechts von Nut 20mm entfernt 15mm Abstand 6mm Durchmesser 10mm tief"},
        ],
    },
    "teil_definitionen": [{
        "id": "platte", "type": "box", "params": {"x": 160, "y": 80, "z": 15}, "orientation": "standard",
        "features": [
            {"id": "nut_oben", "type": "slot", "params": {"width": 5, "depth": 3, "length": None},
             "position": _pos("oben", notes="entlang Y"), "operation": "subtract"},
            {"id": "bohrungen_rechts", "type": "hole_pattern_linear",
             "params": {"count": 4, "spacing": 15, "start_offset": 17.5, "hole_diameter": 6, "depth": 10},
             "position": _pos("oben", edge_distances={"right": 60}, notes="entlang Y"), "operation": "subtract"},
        ],
    }],
    "blueprint": {
        "description": "Platte 160x80x15 mit zentraler Nut und Bohrungsreihe rechts daneben",
        "build_order": ["platte", "nut_oben", "bohrungen_rechts"],
        "features": {
            "platte": {"type": "box", "params": {"x": 160, "y": 80, "z": 15}, "orientation": "standard",
                       "parent": None, "operation": "add", "notes": ""},
            "nut_oben": {"type": "slot", "params": {"width": 5, "depth": 3, "length": None},
                         "parent": "platte", "position": _pos("oben", notes="entlang Y"), "operation": "subtract", "notes": ""},
            "bohrungen_rechts": {"type": "hole_pattern_linear",
                                 "params": {"count": 4, "spacing": 15, "start_offset": 17.5, "hole_diameter": 6, "depth": 10},
                                 "parent": "platte", "position": _pos("oben", edge_distances={"right": 60}, notes="entlang Y"),
                                 "operation": "subtract", "notes": ""},
        },
    },
})


# --- Ex 19: Zwei Platten L-Form mit Bohrung ---
EXAMPLES.append({
    "id": "l_form_platten_bohrung",
    "specification": "platte 100x80x15 rechts eine platte 80x80x15 hochkant buendig zur kante auf der stehenden platte soll oben zentral eine bohrung hin mit 12mm und durchgaengig",
    "inventar": {
        "teil_count": 2,
        "teile": [
            {"id": "basis", "type": "box", "beschreibung": "Grundplatte 100x80x15", "raw_params": {"x": 100, "y": 80, "z": 15}},
            {"id": "wand_rechts", "type": "box", "beschreibung": "Rechte Platte 80x80x15 hochkant", "raw_params": {"x": 80, "y": 80, "z": 15}},
        ],
        "aktionen": [
            {"teil_id": "wand_rechts", "seite": "oben", "beschreibung": "Bohrung zentral 12mm Durchmesser durchgaengig"},
        ],
    },
    "teil_definitionen": [
        {"id": "basis", "type": "box", "params": {"x": 100, "y": 80, "z": 15}, "orientation": "standard", "features": []},
        {"id": "wand_rechts", "type": "box", "params": {"x": 80, "y": 80, "z": 15}, "orientation": "hochkant",
         "features": [
             {"id": "bohrung_wand", "type": "hole_single", "params": {"diameter": 12, "depth": None},
              "position": _pos("oben"), "operation": "subtract"},
         ]},
    ],
    "blueprint": {
        "description": "L-Form: Grundplatte 100x80x15 mit rechts stehender Platte und Bohrung",
        "build_order": ["basis", "wand_rechts", "bohrung_wand"],
        "features": {
            "basis": {"type": "box", "params": {"x": 100, "y": 80, "z": 15}, "orientation": "standard",
                      "parent": None, "operation": "add", "notes": ""},
            "wand_rechts": {"type": "box", "params": {"x": 80, "y": 80, "z": 15}, "orientation": "hochkant",
                            "parent": "basis", "position": _pos("rechts"), "operation": "add", "notes": ""},
            "bohrung_wand": {"type": "hole_single", "params": {"diameter": 12, "depth": None},
                             "parent": "wand_rechts", "position": _pos("oben"), "operation": "subtract", "notes": ""},
        },
    },
})


# --- Ex 20: Platte flach mit Nuten auf Seitenflächen ---
EXAMPLES.append({
    "id": "platte_seitennuten",
    "specification": "block 80x60x30 rechts eine nut 4mm breit 3mm tief entlang der z-achse links eine nut 4mm breit 3mm tief entlang y",
    "inventar": {
        "teil_count": 1,
        "teile": [{"id": "block", "type": "box", "beschreibung": "Block 80x60x30", "raw_params": {"x": 80, "y": 60, "z": 30}}],
        "aktionen": [
            {"teil_id": "block", "seite": "rechts", "beschreibung": "Nut 4mm breit 3mm tief entlang der Z-Achse"},
            {"teil_id": "block", "seite": "links", "beschreibung": "Nut 4mm breit 3mm tief entlang Y"},
        ],
    },
    "teil_definitionen": [{
        "id": "block", "type": "box", "params": {"x": 80, "y": 60, "z": 30}, "orientation": "standard",
        "features": [
            {"id": "nut_rechts", "type": "slot", "params": {"width": 4, "depth": 3, "length": None},
             "position": _pos("rechts", notes="entlang Z"), "operation": "subtract"},
            {"id": "nut_links", "type": "slot", "params": {"width": 4, "depth": 3, "length": None},
             "position": _pos("links", notes="entlang Y"), "operation": "subtract"},
        ],
    }],
    "blueprint": {
        "description": "Block 80x60x30 mit Nut rechts (entlang Z) und links (entlang Y)",
        "build_order": ["block", "nut_rechts", "nut_links"],
        "features": {
            "block": {"type": "box", "params": {"x": 80, "y": 60, "z": 30}, "orientation": "standard",
                      "parent": None, "operation": "add", "notes": ""},
            "nut_rechts": {"type": "slot", "params": {"width": 4, "depth": 3, "length": None},
                           "parent": "block", "position": _pos("rechts", notes="entlang Z"), "operation": "subtract", "notes": ""},
            "nut_links": {"type": "slot", "params": {"width": 4, "depth": 3, "length": None},
                          "parent": "block", "position": _pos("links", notes="entlang Y"), "operation": "subtract", "notes": ""},
        },
    },
})


# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    out_path = Path(__file__).parent / "examples.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(EXAMPLES, f, ensure_ascii=False, indent=2)
    print(f"Generated {len(EXAMPLES)} examples → {out_path}")
    # Stats
    single = sum(1 for e in EXAMPLES if e["inventar"]["teil_count"] == 1)
    multi = sum(1 for e in EXAMPLES if e["inventar"]["teil_count"] > 1)
    print(f"  Single-part: {single}, Multi-part: {multi}")
    feat_types = set()
    for e in EXAMPLES:
        for td in e["teil_definitionen"]:
            for f in td.get("features", []):
                feat_types.add(f["type"])
    print(f"  Feature types covered: {sorted(feat_types)}")
