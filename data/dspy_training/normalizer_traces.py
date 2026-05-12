"""
normalizer_traces.py — direct Normalizer seed cases.

The normalizer runtime contract is NOT final SemanticFeature JSON. It emits
one fixed-vocabulary short form:

  typ: ...
  seite: ...
  position: ...
  richtung: ...
  parameter: key=wert, ...

`feature_builder` turns that short form into the SemanticFeature. These seeds
fill gaps that are rare in the broader projected trace corpus.
"""

from __future__ import annotations


TRACES = [
    {
        "id": "norm_pocket_right_edge_plus_center_offset",
        "input": {
            "beschreibung": (
                "Tasche 30x20x10 deren rechte kante 25mm von rechter "
                "wuerfelkante und 10mm aus mitte nach oben"
            ),
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 100, "y": 100, "z": 50},
            "specification": (
                "100mm wuerfel, oben eine tasche 30x20x10 deren rechte "
                "kante 25mm von rechter wuerfelkante und 10mm aus mitte "
                "nach oben"
            ),
        },
        "expected": (
            "typ: tasche\n"
            "seite: oben\n"
            "position: von_kanten\n"
            "parameter: laenge=30, breite=20, tiefe=10, "
            "kante_rechts=25, versatz_oben=10"
        ),
    },
    {
        "id": "norm_pocket_top_left_edge_to_edge",
        "input": {
            "beschreibung": (
                "Tasche 28x18x6, obere kante der tasche 11mm von oben, "
                "linke seite der tasche 17mm von links"
            ),
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 90, "y": 70, "z": 20},
            "specification": "90x70x20 platte mit tasche oben",
        },
        "expected": (
            "typ: tasche\n"
            "seite: oben\n"
            "position: von_kanten\n"
            "parameter: laenge=28, breite=18, tiefe=6, "
            "kante_oben=11, kante_links=17"
        ),
    },
    {
        "id": "norm_pocket_bottom_right_edge_to_edge",
        "input": {
            "beschreibung": (
                "Tasche 30x20x5 deren rechte kante 5mm und untere kante "
                "3mm von der plattenkante entfernt"
            ),
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 60, "y": 40, "z": 10},
            "specification": "platte oben mit tasche an rechter und unterer kante",
        },
        "expected": (
            "typ: tasche\n"
            "seite: oben\n"
            "position: von_kanten\n"
            "parameter: laenge=30, breite=20, tiefe=5, "
            "kante_rechts=5, kante_unten=3"
        ),
    },
    {
        "id": "norm_pocket_front_back_edges_on_side_face",
        "input": {
            "beschreibung": (
                "rechts eine tasche 34x22x7 deren vordere kante 9mm von "
                "vorne und hintere kante 12mm von hinten entfernt"
            ),
            "seite": "rechts",
            "teil_type": "box",
            "teil_params": {"x": 160, "y": 80, "z": 35},
            "specification": "quader, rechts eine tasche mit front/back kanten",
        },
        "expected": (
            "typ: tasche\n"
            "seite: rechts\n"
            "position: von_kanten\n"
            "parameter: laenge=34, breite=22, tiefe=7, "
            "kante_vorne=9, kante_hinten=12"
        ),
    },
    {
        "id": "norm_pocket_rotation_positive",
        "input": {
            "beschreibung": "Tasche 40x20 mit 8mm tiefe 30 grad gedreht",
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 100, "y": 80, "z": 20},
            "specification": "oben eine gedrehte tasche",
        },
        "expected": (
            "typ: tasche\n"
            "seite: oben\n"
            "position: zentriert\n"
            "parameter: laenge=40, breite=20, tiefe=8, drehung=30"
        ),
    },
    {
        "id": "norm_pocket_height_word_as_depth",
        "input": {
            "beschreibung": "Tasche 40x20 mit 8mm hoehe zentral",
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 100, "y": 80, "z": 20},
            "specification": "oben eine tasche 40x20 mit 8mm hoehe",
        },
        "expected": (
            "typ: tasche\n"
            "seite: oben\n"
            "position: zentriert\n"
            "parameter: laenge=40, breite=20, tiefe=8"
        ),
    },
    {
        "id": "norm_slot_y_axis_edge_distances",
        "input": {
            "beschreibung": (
                "Nut 5x5 entlang y-achse laenge 40mm von oberer kante "
                "30mm und von linker kante 20mm entfernt"
            ),
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 100, "y": 100, "z": 20},
            "specification": "oben eine nut entlang y mit kantenabstand",
        },
        "expected": (
            "typ: nut\n"
            "seite: oben\n"
            "position: von_kanten\n"
            "richtung: y\n"
            "parameter: breite=5, tiefe=5, laenge=40, "
            "abstand_oben=30, abstand_links=20"
        ),
    },
    {
        "id": "norm_slot_z_axis_right_face",
        "input": {
            "beschreibung": "Nut 4mm breit 3mm tief entlang z von mitte 10mm nach oben",
            "seite": "rechts",
            "teil_type": "box",
            "teil_params": {"x": 80, "y": 60, "z": 120},
            "specification": "rechts eine nut entlang z mit versatz",
        },
        "expected": (
            "typ: nut\n"
            "seite: rechts\n"
            "position: von_mitte\n"
            "richtung: z\n"
            "parameter: breite=4, tiefe=3, versatz_oben=10"
        ),
    },
    {
        "id": "norm_slot_flush_right_edge_with_offset",
        "input": {
            "beschreibung": (
                "Nut 5x5 entlang y-achse laenge 40mm liegt auf rechter "
                "kante an 10mm nach oben versetzt"
            ),
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 100, "y": 100, "z": 20},
            "specification": "oben eine nut liegt auf rechter kante an",
        },
        "expected": (
            "typ: nut\n"
            "seite: oben\n"
            "position: von_kanten\n"
            "richtung: y\n"
            "parameter: breite=5, tiefe=5, laenge=40, "
            "kante_rechts=0, versatz_oben=10"
        ),
    },
    {
        "id": "norm_hole_center_offset_two_axes",
        "input": {
            "beschreibung": "9mm Bohrung mit Versatz 16mm nach rechts und 24mm nach oben",
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 110, "y": 110, "z": 110},
            "specification": "oben eine bohrung mit versatz",
        },
        "expected": (
            "typ: bohrung\n"
            "seite: oben\n"
            "position: von_mitte\n"
            "parameter: durchmesser=9, versatz_rechts=16, versatz_oben=24"
        ),
    },
    {
        "id": "norm_hole_center_offset_left_bottom",
        "input": {
            "beschreibung": "7mm Bohrung 19mm nach links und 26mm nach unten verschoben",
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 85, "y": 85, "z": 85},
            "specification": "oben ein loch nach links und unten verschoben",
        },
        "expected": (
            "typ: bohrung\n"
            "seite: oben\n"
            "position: von_mitte\n"
            "parameter: durchmesser=7, versatz_links=19, versatz_unten=26"
        ),
    },
    {
        "id": "norm_hole_center_offset_front",
        "input": {
            "beschreibung": "Bohrung 8mm durch 12mm nach vorne aus der mitte versetzt",
            "seite": "rechts",
            "teil_type": "box",
            "teil_params": {"x": 80, "y": 60, "z": 120},
            "specification": "rechts eine bohrung nach vorne versetzt",
        },
        "expected": (
            "typ: bohrung\n"
            "seite: rechts\n"
            "position: von_mitte\n"
            "parameter: durchmesser=8, tiefe=durch, versatz_vorne=12"
        ),
    },
    {
        "id": "norm_hole_center_offset_back",
        "input": {
            "beschreibung": "Bohrung 8mm durch 14mm nach hinten aus der mitte versetzt",
            "seite": "links",
            "teil_type": "box",
            "teil_params": {"x": 80, "y": 60, "z": 120},
            "specification": "links eine bohrung nach hinten versetzt",
        },
        "expected": (
            "typ: bohrung\n"
            "seite: links\n"
            "position: von_mitte\n"
            "parameter: durchmesser=8, tiefe=durch, versatz_hinten=14"
        ),
    },
    {
        "id": "norm_hole_bottom_front_back_edges",
        "input": {
            "beschreibung": "Bohrung 6mm von vorne 8mm von hinten 10 tief",
            "seite": "unten",
            "teil_type": "box",
            "teil_params": {"x": 80, "y": 50, "z": 20},
            "specification": "unten eine bohrung mit front/back abstand",
        },
        "expected": (
            "typ: bohrung\n"
            "seite: unten\n"
            "position: von_kanten\n"
            "parameter: durchmesser=6, tiefe=10, "
            "abstand_vorne=6, abstand_hinten=8"
        ),
    },
    {
        "id": "norm_hole_side_override_from_text",
        "input": {
            "beschreibung": "links eine bohrung zentral 15mm durchmesser durchgaengig",
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 100, "y": 80, "z": 60},
            "specification": "oben im inventar, text nennt links",
        },
        "expected": (
            "typ: bohrung\n"
            "seite: links\n"
            "position: zentriert\n"
            "parameter: durchmesser=15, tiefe=durch"
        ),
    },
    {
        "id": "norm_pattern_lochkreis_teilkreis",
        "input": {
            "beschreibung": (
                "Lochkreis mit 6 bohrungen 8mm durchmesser 5 tief auf "
                "einem teilkreis von 60mm"
            ),
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 100, "y": 100, "z": 20},
            "specification": "oben ein lochkreis auf teilkreis",
        },
        "expected": (
            "typ: lochkreis\n"
            "seite: oben\n"
            "position: zentriert\n"
            "parameter: kreis_durchmesser=60, anzahl=6, "
            "bohr_durchmesser=8, tiefe=5"
        ),
    },
    {
        "id": "norm_pattern_eckbohrungen_abstand_kante",
        "input": {
            "beschreibung": "4 eckbohrungen jeweils 15mm von den kanten entfernt 8mm durchmesser",
            "seite": "vorne",
            "teil_type": "box",
            "teil_params": {"x": 100, "y": 20, "z": 80},
            "specification": "vorne eckbohrungen",
        },
        "expected": (
            "typ: eckbohrungen\n"
            "seite: vorne\n"
            "position: von_kanten\n"
            "parameter: anzahl=4, abstand_kante=15, bohr_durchmesser=8"
        ),
    },
    {
        "id": "norm_pattern_bohrungsreihe_y",
        "input": {
            "beschreibung": "5 bohrungen entlang der y-achse mit 12mm abstand 4mm durchmesser",
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 100, "y": 100, "z": 20},
            "specification": "oben bohrungsreihe entlang y",
        },
        "expected": (
            "typ: bohrungsreihe\n"
            "seite: oben\n"
            "position: zentriert\n"
            "richtung: y\n"
            "parameter: anzahl=5, abstand=12, bohr_durchmesser=4"
        ),
    },
    {
        "id": "norm_chamfer_top_edges",
        "input": {
            "beschreibung": "Fase 2mm an allen oberen kanten",
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 100, "y": 80, "z": 20},
            "specification": "oben fase an oberen kanten",
        },
        "expected": (
            "typ: fase\n"
            "seite: oben\n"
            "position: zentriert\n"
            "parameter: groesse=2, kanten=alle_oberen"
        ),
    },
    {
        "id": "norm_fillet_vertical_edges",
        "input": {
            "beschreibung": "Rundung 3mm an den vertikalen kanten",
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 100, "y": 80, "z": 20},
            "specification": "rundung an vertikalen kanten",
        },
        "expected": (
            "typ: rundung\n"
            "seite: oben\n"
            "position: zentriert\n"
            "parameter: radius=3, kanten=vertikal"
        ),
    },
    {
        "id": "norm_shell_top_open",
        "input": {
            "beschreibung": "oben aushoehlen mit 2mm wandstaerke",
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 100, "y": 80, "z": 40},
            "specification": "box oben aushoehlen",
        },
        "expected": (
            "typ: aushoelung\n"
            "seite: oben\n"
            "position: zentriert\n"
            "parameter: dicke=2"
        ),
    },
]
