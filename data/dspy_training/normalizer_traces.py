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

    # ── Slot Gap-Filler 2026-05-12: N_kombo-Konvention "AxB entlang ... laenge X"
    # AxB = breite × tiefe (immer), Laenge wird EXPLIZIT als
    # "laenge Xmm" oder "X lang" angegeben — niemals "X tief" nach
    # einem AxB-Pair, das waere doppelt belegt. Frueher hatten wir
    # Traces wie "nut 30x5 entlang x 3 tief" — gleiche Phrasierung,
    # andere Bedeutung. Das brach die Konvention; Modell patzte zurecht.
    {
        "id": "norm_slot_axb_entlang_laenge_versatz",
        "input": {
            "beschreibung": (
                "auf der platte oben eine nut 5x3 entlang x-achse laenge 30mm "
                "8mm nach rechts versetzt"
            ),
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 60, "y": 40, "z": 10},
            "specification": (
                "100mm wuerfel, oben eine platte 60x40x10 zentral, "
                "auf der platte oben eine nut 5x3 entlang x-achse laenge 30mm "
                "8mm nach rechts versetzt"
            ),
        },
        "expected": (
            "typ: nut\n"
            "seite: oben\n"
            "position: von_mitte\n"
            "richtung: x\n"
            "parameter: breite=5, tiefe=3, laenge=30, versatz_rechts=8"
        ),
    },
    {
        "id": "norm_slot_axb_entlang_laenge_zentral",
        "input": {
            "beschreibung": "nut 6x4 entlang y-achse laenge 40mm zentral",
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 100, "y": 100, "z": 20},
            "specification": "100mm wuerfel, oben eine nut 6x4 entlang y-achse laenge 40mm zentral",
        },
        "expected": (
            "typ: nut\n"
            "seite: oben\n"
            "position: zentriert\n"
            "richtung: y\n"
            "parameter: breite=6, tiefe=4, laenge=40"
        ),
    },
    {
        "id": "norm_slot_axb_entlang_laenge_rotation_ccw",
        "input": {
            "beschreibung": (
                "nut 5x3 entlang y-achse laenge 30mm 15 grad gegen uhrzeigersinn"
            ),
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 100, "y": 100, "z": 20},
            "specification": "100mm wuerfel, oben eine nut 5x3 entlang y-achse laenge 30mm 15 grad gegen uhrzeigersinn gedreht",
        },
        "expected": (
            "typ: nut\n"
            "seite: oben\n"
            "position: zentriert\n"
            "richtung: y\n"
            "parameter: breite=5, tiefe=3, laenge=30, drehung=15"
        ),
    },
    {
        "id": "norm_slot_axb_entlang_laenge_kante",
        "input": {
            "beschreibung": (
                "nut 4x2 entlang x-achse laenge 25mm von oberer kante 10mm entfernt"
            ),
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 80, "y": 80, "z": 20},
            "specification": "80mm wuerfel, oben eine nut 4x2 entlang x-achse laenge 25mm von oberer kante 10mm entfernt",
        },
        "expected": (
            "typ: nut\n"
            "seite: oben\n"
            "position: von_kanten\n"
            "richtung: x\n"
            "parameter: breite=4, tiefe=2, laenge=25, abstand_oben=10"
        ),
    },

    # ── Slot: weitere Rotation-Konvention + Side-Face Variationen ────────
    {
        "id": "norm_slot_axb_entlang_laenge_rotation_cw",
        "input": {
            "beschreibung": (
                "nut 5x3 entlang x-achse laenge 30mm 20 grad im uhrzeigersinn"
            ),
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 100, "y": 100, "z": 20},
            "specification": "100mm wuerfel, oben eine nut 5x3 entlang x-achse laenge 30mm 20 grad im uhrzeigersinn gedreht",
        },
        "expected": (
            "typ: nut\n"
            "seite: oben\n"
            "position: zentriert\n"
            "richtung: x\n"
            "parameter: breite=5, tiefe=3, laenge=30, drehung=-20"
        ),
    },
    {
        "id": "norm_slot_on_side_face_vertical",
        "input": {
            "beschreibung": "nut 5x4 entlang z-achse laenge 40mm mittig",
            "seite": "rechts",
            "teil_type": "box",
            "teil_params": {"x": 100, "y": 100, "z": 100},
            "specification": "100mm wuerfel, rechts eine nut 5x4 entlang z-achse laenge 40mm mittig",
        },
        "expected": (
            "typ: nut\n"
            "seite: rechts\n"
            "position: zentriert\n"
            "richtung: z\n"
            "parameter: breite=5, tiefe=4, laenge=40"
        ),
    },

    # ── Lochkreis: weitere Varianten (heutige Coverage: 1) ───────────────
    {
        "id": "norm_pattern_lochkreis_with_offset",
        "input": {
            "beschreibung": (
                "lochkreis mit 4 bohrungen 6mm durchmesser 4 tief auf einem "
                "teilkreis von 40mm, 15mm nach rechts und 10mm nach oben versetzt"
            ),
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 100, "y": 100, "z": 20},
            "specification": "100mm wuerfel, oben ein lochkreis mit 4 bohrungen 6mm durchmesser 4 tief auf einem teilkreis von 40mm 15mm nach rechts und 10mm nach oben versetzt",
        },
        "expected": (
            "typ: lochkreis\n"
            "seite: oben\n"
            "position: von_mitte\n"
            "parameter: anzahl=4, durchmesser=6, tiefe=4, "
            "kreis_durchmesser=40, versatz_rechts=15, versatz_oben=10"
        ),
    },
    {
        "id": "norm_pattern_lochkreis_durchgaengig",
        "input": {
            "beschreibung": (
                "lochkreis 70mm mit 8 bohrungen 12mm durchmesser durchgaengig"
            ),
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 120, "y": 120, "z": 20},
            "specification": "120mm wuerfel, oben ein lochkreis 70mm mit 8 bohrungen 12mm durchmesser durchgaengig",
        },
        "expected": (
            "typ: lochkreis\n"
            "seite: oben\n"
            "position: zentriert\n"
            "parameter: anzahl=8, durchmesser=12, kreis_durchmesser=70"
        ),
    },

    # ── Eckbohrungen: weitere Varianten (heutige Coverage: 1) ────────────
    {
        "id": "norm_pattern_eckbohrungen_an_jeder_ecke",
        "input": {
            "beschreibung": (
                "an jeder ecke eine bohrung je 20mm von den kanten entfernt "
                "6mm durchmesser"
            ),
            "seite": "vorne",
            "teil_type": "box",
            "teil_params": {"x": 100, "y": 80, "z": 60},
            "specification": "100x80x60 wuerfel, vorne an jeder ecke eine bohrung je 20mm von den kanten entfernt 6mm durchmesser",
        },
        "expected": (
            "typ: eckbohrungen\n"
            "seite: vorne\n"
            "position: von_kanten\n"
            "parameter: durchmesser=6, abstand_kante=20"
        ),
    },
    {
        "id": "norm_pattern_eckbohrungen_grid_2x2_randabstand",
        "input": {
            "beschreibung": (
                "ein 2x2 lochmuster mit 8mm bohrungen 5 tief, "
                "randabstand 10mm zur kante"
            ),
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 100, "y": 100, "z": 20},
            "specification": "100mm wuerfel, oben ein 2x2 lochmuster mit 8mm bohrungen 5 tief randabstand 10mm zur kante",
        },
        "expected": (
            "typ: eckbohrungen\n"
            "seite: oben\n"
            "position: von_kanten\n"
            "parameter: anzahl=4, durchmesser=8, tiefe=5, abstand_kante=10"
        ),
    },

    # ── Bohrungsreihe: weitere Varianten ─────────────────────────────────
    {
        "id": "norm_pattern_bohrungsreihe_mit_anker",
        "input": {
            "beschreibung": (
                "lochreihe entlang x mit 5 bohrungen 8mm durchmesser 5 tief, "
                "abstand 15mm, startversatz 10mm, ankerpunkt obere rechte "
                "ecke 10mm nach unten versetzt"
            ),
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 100, "y": 100, "z": 20},
            "specification": "100mm wuerfel, oben eine lochreihe entlang x mit 5 bohrungen 8mm durchmesser 5 tief, abstand 15mm, startversatz 10mm, ankerpunkt obere rechte ecke 10mm nach unten versetzt",
        },
        "expected": (
            "typ: bohrungsreihe\n"
            "seite: oben\n"
            "position: von_kanten\n"
            "richtung: x\n"
            "parameter: anzahl=5, durchmesser=8, tiefe=5, abstand=15, "
            "versatz_unten=10"
        ),
    },
    {
        "id": "norm_pattern_bohrungsreihe_z_axis_rechts",
        "input": {
            "beschreibung": (
                "4 loecher der reihe nach entlang z mit 15mm abstand "
                "6mm durchmesser"
            ),
            "seite": "rechts",
            "teil_type": "box",
            "teil_params": {"x": 80, "y": 60, "z": 120},
            "specification": "rechts 4 loecher der reihe nach entlang z mit 15mm abstand 6mm durchmesser",
        },
        "expected": (
            "typ: bohrungsreihe\n"
            "seite: rechts\n"
            "position: zentriert\n"
            "richtung: z\n"
            "parameter: anzahl=4, durchmesser=6, abstand=15"
        ),
    },

    # ── Fase: weitere Varianten (heutige Coverage: 1) ────────────────────
    {
        "id": "norm_chamfer_single_edge_size",
        "input": {
            "beschreibung": "rechts eine fase 3mm",
            "seite": "rechts",
            "teil_type": "box",
            "teil_params": {"x": 50, "y": 50, "z": 50},
            "specification": "50mm wuerfel, rechts eine fase 3mm",
        },
        "expected": (
            "typ: fase\n"
            "seite: rechts\n"
            "position: zentriert\n"
            "parameter: groesse=3"
        ),
    },
    {
        "id": "norm_chamfer_alle_kanten",
        "input": {
            "beschreibung": "alle kanten mit fase 1.5mm",
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 50, "y": 50, "z": 50},
            "specification": "50mm wuerfel, vorne alle kanten mit fase 1.5mm",
        },
        "expected": (
            "typ: fase\n"
            "seite: oben\n"
            "position: zentriert\n"
            "parameter: groesse=1.5"
        ),
    },
    {
        "id": "norm_chamfer_kantenlaenge_wording",
        "input": {
            "beschreibung": "eine fase mit kantenlaenge 4mm",
            "seite": "hinten",
            "teil_type": "box",
            "teil_params": {"x": 80, "y": 50, "z": 40},
            "specification": "80x50x40 wuerfel, hinten eine fase mit kantenlaenge 4mm",
        },
        "expected": (
            "typ: fase\n"
            "seite: hinten\n"
            "position: zentriert\n"
            # "kantenlaenge" der Fase = die Schenkellaenge = groesse
            "parameter: groesse=4"
        ),
    },

    # ── Rundung: weitere Varianten (heutige Coverage: 1) ─────────────────
    {
        "id": "norm_fillet_radius_simple",
        "input": {
            "beschreibung": "unten eine rundung radius 4mm",
            "seite": "unten",
            "teil_type": "box",
            "teil_params": {"x": 50, "y": 50, "z": 50},
            "specification": "50mm wuerfel, unten eine rundung radius 4mm",
        },
        "expected": (
            "typ: rundung\n"
            "seite: unten\n"
            "position: zentriert\n"
            "parameter: radius=4"
        ),
    },
    {
        "id": "norm_fillet_abrunden_wording",
        "input": {
            "beschreibung": "alle kanten 2mm abrunden",
            "seite": "vorne",
            "teil_type": "box",
            "teil_params": {"x": 50, "y": 50, "z": 50},
            "specification": "50mm wuerfel, vorne alle kanten 2mm abrunden",
        },
        "expected": (
            "typ: rundung\n"
            "seite: vorne\n"
            "position: zentriert\n"
            "parameter: radius=2"
        ),
    },
    {
        "id": "norm_fillet_kantenradius_wording",
        "input": {
            "beschreibung": "kantenradius 3mm",
            "seite": "hinten",
            "teil_type": "box",
            "teil_params": {"x": 50, "y": 50, "z": 50},
            "specification": "50mm wuerfel, hinten kantenradius 3mm",
        },
        "expected": (
            "typ: rundung\n"
            "seite: hinten\n"
            "position: zentriert\n"
            "parameter: radius=3"
        ),
    },

    # ── Bohrung: durchgehend + simple-mittig + AxB-Notation ──────────────
    {
        "id": "norm_hole_through_simple",
        "input": {
            "beschreibung": "bohrung 10mm durchmesser durchgaengig mittig",
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 60, "y": 60, "z": 30},
            "specification": "60mm wuerfel, oben eine bohrung 10mm durchmesser durchgaengig mittig",
        },
        "expected": (
            "typ: bohrung\n"
            "seite: oben\n"
            "position: zentriert\n"
            "parameter: durchmesser=10, tiefe=durch"
        ),
    },
    {
        "id": "norm_hole_with_depth_and_edge_distance",
        "input": {
            "beschreibung": (
                "bohrung 18mm 10mm von oberer kante, 90mm aus mitte nach "
                "links, 10 tief"
            ),
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 200, "y": 200, "z": 200},
            "specification": "200mm wuerfel, oben eine 18mm bohrung 10mm von oberer kante, 90mm aus mitte nach links, 10 tief",
        },
        "expected": (
            "typ: bohrung\n"
            "seite: oben\n"
            "position: von_mitte\n"
            "parameter: durchmesser=18, tiefe=10, abstand_oben=10, "
            "versatz_links=90"
        ),
    },

    # ── Tasche: bottom-face + plate-on-cube + diagonal-anker ─────────────
    {
        "id": "norm_pocket_bottom_face_simple",
        "input": {
            "beschreibung": "tasche 40x30x6 zentral",
            "seite": "unten",
            "teil_type": "box",
            "teil_params": {"x": 80, "y": 80, "z": 30},
            "specification": "80mm wuerfel, unten eine tasche 40x30x6 zentral",
        },
        "expected": (
            "typ: tasche\n"
            "seite: unten\n"
            "position: zentriert\n"
            "parameter: laenge=40, breite=30, tiefe=6"
        ),
    },
    # (Anker-Faelle gehoeren NICHT in den Normalizer-`parameter`-Bereich —
    # `_apply_phrase_anchor` liest den Anker aus der beschreibung. Daher
    # hier kein anker-Demo; der Normalizer liefert nur typ/seite/position/
    # parameter mit dem Standard-Vokabular.)

    # ── Aushoelung: zusaetzliche Wording-Variante ────────────────────────
    {
        "id": "norm_shell_thickness_explicit",
        "input": {
            "beschreibung": "bauteil mit 3mm wandstaerke aushoehlen",
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 60, "y": 60, "z": 60},
            "specification": "60mm wuerfel, oben bauteil mit 3mm wandstaerke aushoehlen",
        },
        "expected": (
            "typ: aushoelung\n"
            "seite: oben\n"
            "position: zentriert\n"
            "parameter: dicke=3"
        ),
    },

    # ── "jeweils von den kanten X" Bedeutungs-Disambiguierung ────────────
    # Regel: bei SINGLE-Bohrung an Eck-Position ("unten rechts ... jeweils
    # X von den kanten") sind nur die ZWEI impliziten Kanten gemeint, nicht
    # alle vier. "Alle vier" gilt nur explizit bei "eckbohrungen", "an jeder
    # ecke" oder "an allen kanten". Heatmap 2026-05-12 zeigte Normalizer
    # generalisierte "jeweils" hier ueber — fuegte abstand_oben=10 zu einer
    # unten-rechts-Bohrung hinzu (run bef297ca).
    {
        "id": "norm_hole_corner_unten_rechts_jeweils_two_edges",
        "input": {
            "beschreibung": (
                "oben soll unten rechts eine 18mm bohrung jeweils von den "
                "kanten 10mm entfernt mit 10mm tiefe hin"
            ),
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 200, "y": 200, "z": 200},
            "specification": (
                "200mm wuerfel, oben soll unten rechts eine 18mm bohrung "
                "jeweils von den kanten 10mm entfernt mit 10mm tiefe hin"
            ),
        },
        "expected": (
            "typ: bohrung\n"
            "seite: oben\n"
            "position: von_kanten\n"
            "parameter: durchmesser=18, tiefe=10, "
            "abstand_unten=10, abstand_rechts=10"
        ),
    },
    {
        "id": "norm_hole_corner_oben_links_jeweils_two_edges",
        "input": {
            "beschreibung": (
                "oben links eine 12mm bohrung jeweils 15mm von den kanten entfernt 8 tief"
            ),
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 150, "y": 150, "z": 50},
            "specification": "150mm wuerfel, oben links eine 12mm bohrung jeweils 15mm von den kanten entfernt 8 tief",
        },
        "expected": (
            "typ: bohrung\n"
            "seite: oben\n"
            "position: von_kanten\n"
            "parameter: durchmesser=12, tiefe=8, "
            "abstand_oben=15, abstand_links=15"
        ),
    },
    {
        "id": "norm_hole_corner_oben_rechts_jeweils_two_edges",
        "input": {
            "beschreibung": (
                "oben soll oben rechts jeweils von den kanten 10mm entfernt "
                "eine 18mm bohrung 10 tief hin"
            ),
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 200, "y": 200, "z": 200},
            "specification": (
                "200mm wuerfel, oben soll oben rechts jeweils von den "
                "kanten 10mm entfernt eine 18mm bohrung 10 tief hin"
            ),
        },
        "expected": (
            "typ: bohrung\n"
            "seite: oben\n"
            "position: von_kanten\n"
            "parameter: durchmesser=18, tiefe=10, "
            "abstand_oben=10, abstand_rechts=10"
        ),
    },
    # Gegenstueck: "an jeder ecke" / eckbohrungen sind die EINZIGEN Faelle
    # die "alle 4 kanten" rechtfertigen.
    {
        "id": "norm_pattern_an_jeder_ecke_four_edges_via_abstand_kante",
        "input": {
            "beschreibung": (
                "an jeder ecke eine 8mm bohrung jeweils 12mm von den kanten "
                "entfernt 5 tief"
            ),
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 100, "y": 100, "z": 20},
            "specification": "100mm wuerfel, oben an jeder ecke eine 8mm bohrung jeweils 12mm von den kanten entfernt 5 tief",
        },
        "expected": (
            "typ: eckbohrungen\n"
            "seite: oben\n"
            "position: von_kanten\n"
            "parameter: durchmesser=8, tiefe=5, abstand_kante=12"
        ),
    },
    {
        "id": "norm_v2_hole_top_center",
        "input": {
            "beschreibung": "oben eine 8mm bohrung zentral 10 tief",
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 120, "y": 90, "z": 50},
            "specification": "V2 palette top centered hole",
        },
        "expected": (
            "typ: bohrung\n"
            "seite: oben\n"
            "position: zentriert\n"
            "parameter: durchmesser=8, tiefe=10"
        ),
    },
    {
        "id": "norm_v2_hole_bottom_front_right_edges",
        "input": {
            "beschreibung": (
                "unten vorne rechts eine 6mm bohrung jeweils 12mm von den "
                "kanten entfernt 8 tief"
            ),
            "seite": "unten",
            "teil_type": "box",
            "teil_params": {"x": 120, "y": 90, "z": 50},
            "specification": "V2 palette bottom face corner hole",
        },
        "expected": (
            "typ: bohrung\n"
            "seite: unten\n"
            "position: von_kanten\n"
            "parameter: durchmesser=6, tiefe=8, "
            "abstand_vorne=12, abstand_rechts=12"
        ),
    },
    {
        "id": "norm_v2_hole_right_edge_plus_up",
        "input": {
            "beschreibung": (
                "rechts eine 7mm bohrung von rechter kante 20mm entfernt "
                "und 8mm nach oben versetzt 9 tief"
            ),
            "seite": "rechts",
            "teil_type": "box",
            "teil_params": {"x": 120, "y": 90, "z": 50},
            "specification": "V2 palette right face mixed positioning",
        },
        "expected": (
            "typ: bohrung\n"
            "seite: rechts\n"
            "position: von_kanten\n"
            "parameter: durchmesser=7, tiefe=9, "
            "abstand_rechts=20, versatz_oben=8"
        ),
    },
    {
        "id": "norm_v2_pocket_top_edge_to_edge",
        "input": {
            "beschreibung": (
                "oben eine tasche 30x20x6 deren rechte kante 25mm von "
                "rechter wuerfelkante und untere kante 10mm von unterer "
                "wuerfelkante entfernt"
            ),
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 120, "y": 90, "z": 50},
            "specification": "V2 palette pocket edge-to-edge",
        },
        "expected": (
            "typ: tasche\n"
            "seite: oben\n"
            "position: von_kanten\n"
            "parameter: laenge=30, breite=20, tiefe=6, "
            "kante_rechts=25, kante_unten=10"
        ),
    },
    {
        "id": "norm_v2_pocket_front_height_rotation_cw",
        "input": {
            "beschreibung": (
                "vorne eine tasche 28x18 mit 5mm hoehe 15mm nach rechts "
                "und 5mm nach oben versetzt 20 grad im uhrzeigersinn gedreht"
            ),
            "seite": "vorne",
            "teil_type": "box",
            "teil_params": {"x": 120, "y": 90, "z": 50},
            "specification": "V2 palette pocket height wording and rotation",
        },
        "expected": (
            "typ: tasche\n"
            "seite: vorne\n"
            "position: von_mitte\n"
            "parameter: laenge=28, breite=18, tiefe=5, "
            "versatz_rechts=15, versatz_oben=5, drehung=-20"
        ),
    },
    {
        "id": "norm_v2_slot_top_y_edge_distances",
        "input": {
            "beschreibung": (
                "oben eine nut 5x3 entlang y-achse laenge 40mm von linker "
                "kante 12mm und von oberer kante 18mm entfernt"
            ),
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 120, "y": 90, "z": 50},
            "specification": "V2 palette slot y axis with edge distances",
        },
        "expected": (
            "typ: nut\n"
            "seite: oben\n"
            "position: von_kanten\n"
            "richtung: y\n"
            "parameter: breite=5, tiefe=3, laenge=40, "
            "abstand_links=12, abstand_oben=18"
        ),
    },
    {
        "id": "norm_v2_slot_right_z_full_offset",
        "input": {
            "beschreibung": "rechts eine nut 4x3 entlang z-achse 10mm nach oben versetzt",
            "seite": "rechts",
            "teil_type": "box",
            "teil_params": {"x": 120, "y": 90, "z": 50},
            "specification": "V2 palette side-face slot without explicit length",
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
        "id": "norm_v2_pattern_lochkreis_offset",
        "input": {
            "beschreibung": (
                "oben lochkreis mit 6 bohrungen 5mm durchmesser 4 tief "
                "auf teilkreis 50mm 10mm nach links und 5mm nach unten versetzt"
            ),
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 120, "y": 90, "z": 50},
            "specification": "V2 palette lochkreis with center offset",
        },
        "expected": (
            "typ: lochkreis\n"
            "seite: oben\n"
            "position: von_mitte\n"
            "parameter: anzahl=6, durchmesser=5, tiefe=4, "
            "kreis_durchmesser=50, versatz_links=10, versatz_unten=5"
        ),
    },
    {
        "id": "norm_v2_pattern_grid_right_2x2",
        "input": {
            "beschreibung": (
                "rechts ein 2x2 lochmuster mit 6mm bohrungen 4 tief "
                "randabstand 8mm zur kante"
            ),
            "seite": "rechts",
            "teil_type": "box",
            "teil_params": {"x": 120, "y": 90, "z": 50},
            "specification": "V2 palette side-face 2x2 lochmuster",
        },
        "expected": (
            "typ: eckbohrungen\n"
            "seite: rechts\n"
            "position: von_kanten\n"
            "parameter: anzahl=4, durchmesser=6, tiefe=4, abstand_kante=8"
        ),
    },
    {
        "id": "norm_v2_pattern_linear_front_z",
        "input": {
            "beschreibung": (
                "vorne eine bohrungsreihe entlang z mit 4 bohrungen 5mm "
                "durchmesser 4 tief abstand 12mm"
            ),
            "seite": "vorne",
            "teil_type": "box",
            "teil_params": {"x": 120, "y": 90, "z": 50},
            "specification": "V2 palette front-face linear pattern",
        },
        "expected": (
            "typ: bohrungsreihe\n"
            "seite: vorne\n"
            "position: zentriert\n"
            "richtung: z\n"
            "parameter: anzahl=4, durchmesser=5, tiefe=4, abstand=12"
        ),
    },
    {
        "id": "norm_v2_plate_hole_edge",
        "input": {
            "beschreibung": (
                "oben eine 5mm bohrung 5 tief von der oberen kante 10mm "
                "und von linker kante 8mm entfernt"
            ),
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 70, "y": 50, "z": 8},
            "specification": "V2 palette feature on plate",
        },
        "expected": (
            "typ: bohrung\n"
            "seite: oben\n"
            "position: von_kanten\n"
            "parameter: durchmesser=5, tiefe=5, "
            "abstand_oben=10, abstand_links=8"
        ),
    },
    {
        "id": "norm_v2_plate_pocket_rotation_ccw",
        "input": {
            "beschreibung": "oben eine tasche 24x16x4 zentral 30 grad gegen uhrzeigersinn gedreht",
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 70, "y": 50, "z": 8},
            "specification": "V2 palette rotated pocket on plate",
        },
        "expected": (
            "typ: tasche\n"
            "seite: oben\n"
            "position: zentriert\n"
            "parameter: laenge=24, breite=16, tiefe=4, drehung=30"
        ),
    },
    {
        "id": "norm_v2_plate_slot_x_offset",
        "input": {
            "beschreibung": "oben eine nut 4x2 entlang x-achse laenge 30mm 6mm nach rechts versetzt",
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 70, "y": 50, "z": 8},
            "specification": "V2 palette slot on plate",
        },
        "expected": (
            "typ: nut\n"
            "seite: oben\n"
            "position: von_mitte\n"
            "richtung: x\n"
            "parameter: breite=4, tiefe=2, laenge=30, versatz_rechts=6"
        ),
    },
]
