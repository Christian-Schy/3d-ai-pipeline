"""
labeler_platzierer_traces.py — Hand-curated traces fuer Phase-1-Punkt-3
Vokabular-Erweiterung (anchor, edge-distance, versatz, "nach aussen").

Erzeugt 18 Trainings-Traces im neuen Schema:
  - position_extractor (Labeler): per-Teil placement_sentences + feature_sentences
  - position_normalizer (Platzierer): per-Kind-Teil normalized output
  - normalizer (Pocket-Cases): per-Aktion feature output

Verwendung:
  python -m data.dspy_training.labeler_platzierer_traces > labeler_platzierer_traces.json
"""
from __future__ import annotations
import json
import sys


def _wuerfel(size: int = 50) -> dict:
    return {
        "id": "wuerfel",
        "type": "box",
        "beschreibung": f"{size}mm Wuerfel",
        "raw_params": {"x": size, "y": size, "z": size},
    }


def _platte(x: int, y: int, z: int, name: str = "platte") -> dict:
    return {
        "id": name,
        "type": "box",
        "beschreibung": f"{x}x{y}x{z} Platte",
        "raw_params": {"x": x, "y": y, "z": z},
    }


def _build_trace(*, tid, spec, child_dims, child_text, placement_sents,
                 normalized, basis_size=50, feature_sents=None,
                 child_name="platte", category="placement",
                 difficulty="P3", aktionen=None, normalizer_pairs=None):
    """Standard-Bauer fuer wuerfel + ein-Kind-Teil-Traces."""
    basis = _wuerfel(basis_size)
    child = _platte(*child_dims, name=child_name)
    inv_aktionen = aktionen or []
    teil_texte = {
        "wuerfel": f"{basis_size}mm wuerfel",
        child_name: child_text,
    }
    pe_positionen = [
        {"teil_id": "wuerfel", "is_root": True,
         "placement_sentences": [], "feature_sentences": []},
        {"teil_id": child_name, "is_root": False,
         "placement_sentences": placement_sents,
         "feature_sentences": feature_sents or []},
    ]
    pn_list = [{
        "teil_id": child_name,
        "input_sentence": " ".join(placement_sents),
        "output": normalized,
    }] if normalized else []
    trace = {
        "id": tid,
        "specification": spec,
        "metadata": {"category": category, "difficulty": difficulty,
                     "sprachstil": "natuerlich"},
        "inventar": {
            "teil_count": 2,
            "teile": [basis, child],
            "aktionen": inv_aktionen,
        },
        "teil_texte": teil_texte,
        "position_extractor": {"positionen": pe_positionen},
        "position_normalizer": pn_list,
    }
    # Optional: normalizer pairs (for pocket cases)
    if normalizer_pairs:
        trace["normalizer_pairs"] = normalizer_pairs
    return trace


# ─────────────────────────────────────────────────────────────────────
# USER-CASES (U1-U5) — exakt wie diktiert
# ─────────────────────────────────────────────────────────────────────

U1 = _build_trace(
    tid="u1_anchor_corner_2dist_cw",
    spec=("wuerfel 50mm, oben drauf platte 100x100x20, 100x20 seite liegt auf, "
          "obere linke ecke von links 10mm und von oben 20mm entfernt, "
          "um 20 grad im uhrzeigersinn gedreht"),
    child_dims=(100, 100, 20),
    child_text=("oben drauf platte 100x100x20, 100x20 seite liegt auf, "
                "obere linke ecke von links 10mm und von oben 20mm entfernt, "
                "um 20 grad im uhrzeigersinn gedreht"),
    placement_sents=[
        "oben drauf platte 100x100x20",
        "100x20 seite liegt auf",
        "obere linke ecke von links 10mm und von oben 20mm entfernt",
        "um 20 grad im uhrzeigersinn gedreht",
    ],
    normalized={
        "parent": "wuerfel",
        "seite": "oben",
        "ausrichtung": "zentriert",
        "orientierung": "hochkant",
        "anliegende_flaeche": "100x20",
        "abstand": {"versatz_rechts": 10, "versatz_unten": 20},
        "winkel": -20.0,
        "anker": "top_left_auf_top_left",
        "pre_rotation": {},
        "notes": "",
    },
    category="anchor_corner",
    difficulty="P5",
)

U2 = _build_trace(
    tid="u2_edge_midpoint_2dist",
    spec=("wuerfel 50mm, oben drauf platte 120x100x20, 20x100 seite liegt auf, "
          "die linke seite der platte von links 20mm und von oben 40mm entfernt"),
    child_dims=(120, 100, 20),
    child_text=("oben drauf platte 120x100x20, 20x100 seite liegt auf, "
                "die linke seite der platte von links 20mm und von oben 40mm entfernt"),
    placement_sents=[
        "oben drauf platte 120x100x20",
        "20x100 seite liegt auf",
        "die linke seite der platte von links 20mm und von oben 40mm entfernt",
    ],
    normalized={
        "parent": "wuerfel",
        "seite": "oben",
        "ausrichtung": "zentriert",
        "orientierung": "hochkant",
        "anliegende_flaeche": "20x100",
        "abstand": {"versatz_rechts": 20, "versatz_unten": 40},
        "winkel": 0,
        "anker": "left_edge_auf_left_edge",
        "pre_rotation": {},
        "notes": "linke kante des kindes auf linker kante des parents, midpoint-bezogen",
    },
    category="anchor_edge",
    difficulty="P5",
)

U3 = _build_trace(
    tid="u3_edge_to_opposite_edges_ccw",
    spec=("wuerfel 50mm, oben drauf platte 40x80x20, 40x20 seite liegt auf, "
          "die obere seite der platte soll von unten 20mm entfernt sein, "
          "die rechte seite der platte soll von rechts 10mm entfernt sein, "
          "um 10 grad gegen uhrzeigersinn rotiert"),
    child_dims=(40, 80, 20),
    child_text=("oben drauf platte 40x80x20, 40x20 seite liegt auf, "
                "die obere seite der platte soll von unten 20mm entfernt sein, "
                "die rechte seite der platte soll von rechts 10mm entfernt sein, "
                "um 10 grad gegen uhrzeigersinn rotiert"),
    placement_sents=[
        "oben drauf platte 40x80x20",
        "40x20 seite liegt auf",
        "die obere seite der platte soll von unten 20mm entfernt sein",
        "die rechte seite der platte soll von rechts 10mm entfernt sein",
        "um 10 grad gegen uhrzeigersinn rotiert",
    ],
    normalized={
        "parent": "wuerfel",
        "seite": "oben",
        "ausrichtung": "von_kanten",
        "orientierung": "hochkant",
        "anliegende_flaeche": "40x20",
        "abstand": {"abstand_unten": 20, "abstand_rechts": 10},
        "winkel": 10.0,
        "anker": "",
        "pre_rotation": {},
        "notes": "obere seite des kindes mit abstand zur unteren kante des parents",
    },
    category="edge_distance",
    difficulty="P5",
)

U4 = _build_trace(
    tid="u4_anchor_corner_same_side_cw",
    spec=("wuerfel 50mm, oben drauf platte 80x80x20, 80x20 seite liegt auf, "
          "obere rechte ecke der platte von der oberen rechten ecke jeweils 10mm entfernt, "
          "um 10 grad im uhrzeigersinn rotiert"),
    child_dims=(80, 80, 20),
    child_text=("oben drauf platte 80x80x20, 80x20 seite liegt auf, "
                "obere rechte ecke der platte von der oberen rechten ecke jeweils 10mm entfernt, "
                "um 10 grad im uhrzeigersinn rotiert"),
    placement_sents=[
        "oben drauf platte 80x80x20",
        "80x20 seite liegt auf",
        "obere rechte ecke der platte von der oberen rechten ecke jeweils 10mm entfernt",
        "um 10 grad im uhrzeigersinn rotiert",
    ],
    normalized={
        "parent": "wuerfel",
        "seite": "oben",
        "ausrichtung": "zentriert",
        "orientierung": "hochkant",
        "anliegende_flaeche": "80x20",
        "abstand": {"versatz_links": 10, "versatz_unten": 10},
        "winkel": -10.0,
        "anker": "top_right_auf_top_right",
        "pre_rotation": {},
        "notes": "diagonal-anker mit symmetrischem abstand",
    },
    category="anchor_corner",
    difficulty="P5",
)

U6 = _build_trace(
    tid="u6_no_anchor_edges_two_axes_rotation",
    spec=("wuerfel 100mm, oben drauf platte 100x100x20, 100x20 seite liegt auf, "
          "obere kante 10mm von oberer kante des wuerfels entfernt, "
          "rechte seite 10mm von rechter seite des wuerfels entfernt, "
          "um 10 grad gedreht"),
    child_dims=(100, 100, 20),
    child_text=("oben drauf platte 100x100x20, 100x20 seite liegt auf, "
                "obere kante 10mm von oberer kante des wuerfels entfernt, "
                "rechte seite 10mm von rechter seite des wuerfels entfernt, "
                "um 10 grad gedreht"),
    placement_sents=[
        "oben drauf platte 100x100x20",
        "100x20 seite liegt auf",
        "obere kante 10mm von oberer kante des wuerfels entfernt",
        "rechte seite 10mm von rechter seite des wuerfels entfernt",
        "um 10 grad gedreht",
    ],
    normalized={
        "parent": "wuerfel",
        "seite": "oben",
        "ausrichtung": "von_kanten",
        "orientierung": "hochkant",
        "anliegende_flaeche": "100x20",
        "abstand": {"abstand_oben": 10, "abstand_rechts": 10},
        "winkel": 10.0,
        "anker": "",
        "pre_rotation": {},
        "notes": "kein anker — reine kanten-distanz",
    },
    basis_size=100, category="edge_distance_no_anchor", difficulty="P4",
)

U7 = _build_trace(
    tid="u7_anchor_corner_with_distances",
    spec=("wuerfel 100mm, rechts platte 100x100x20, 100x20 seite liegt auf, "
          "linke obere ecke der platte von der linken seite 10mm "
          "und von der oberen seite 20mm entfernt, um 20 grad gedreht"),
    child_dims=(100, 100, 20),
    child_text=("rechts platte 100x100x20, 100x20 seite liegt auf, "
                "linke obere ecke der platte von der linken seite 10mm "
                "und von der oberen seite 20mm entfernt, um 20 grad gedreht"),
    placement_sents=[
        "rechts platte 100x100x20",
        "100x20 seite liegt auf",
        "linke obere ecke der platte von der linken seite 10mm und von der oberen seite 20mm entfernt",
        "um 20 grad gedreht",
    ],
    normalized={
        "parent": "wuerfel",
        "seite": "rechts",
        "ausrichtung": "zentriert",
        "orientierung": "hochkant",
        "anliegende_flaeche": "100x20",
        "abstand": {"versatz_rechts": 10, "versatz_unten": 20},
        "winkel": 20.0,
        "anker": "top_left_auf_top_left",
        "pre_rotation": {},
        "notes": "ecke explizit erwaehnt → anker, versatz von ankerpunkt",
    },
    basis_size=100, category="anchor_corner", difficulty="P5",
)

U5 = _build_trace(
    tid="u5_versatz_center_ccw",
    spec=("wuerfel 50mm, oben drauf platte 60x80x20, "
          "um 20mm nach oben versetzt und um 10mm nach links versetzt, "
          "und um 15 grad gegen uhrzeigersinn rotiert"),
    child_dims=(60, 80, 20),
    child_text=("oben drauf platte 60x80x20, "
                "um 20mm nach oben versetzt und um 10mm nach links versetzt, "
                "und um 15 grad gegen uhrzeigersinn rotiert"),
    placement_sents=[
        "oben drauf platte 60x80x20",
        "um 20mm nach oben versetzt und um 10mm nach links versetzt",
        "und um 15 grad gegen uhrzeigersinn rotiert",
    ],
    normalized={
        "parent": "wuerfel",
        "seite": "oben",
        "ausrichtung": "von_mitte",
        "orientierung": "standard",
        "anliegende_flaeche": "keine",
        "abstand": {"versatz_oben": 20, "versatz_links": 10},
        "winkel": 15.0,
        "anker": "",
        "pre_rotation": {},
        "notes": "versatz von der mitte aus, kein anker",
    },
    category="versatz_mitte",
    difficulty="P3",
)


# ─────────────────────────────────────────────────────────────────────
# COVERAGE-CASES (C1-C7) — Variationen die sonst fehlen
# ─────────────────────────────────────────────────────────────────────

C1 = _build_trace(
    tid="c1_centered_simple",
    spec="wuerfel 60mm, oben drauf platte 60x60x10 zentriert",
    child_dims=(60, 60, 10),
    child_text="oben drauf platte 60x60x10 zentriert",
    placement_sents=["oben drauf platte 60x60x10 zentriert"],
    normalized={
        "parent": "wuerfel", "seite": "oben",
        "ausrichtung": "zentriert", "orientierung": "standard",
        "anliegende_flaeche": "keine", "abstand": {},
        "winkel": 0, "anker": "", "pre_rotation": {}, "notes": "",
    },
    basis_size=60, category="trivial", difficulty="P1",
)

C2 = _build_trace(
    tid="c2_flush_corner_no_distance",
    spec="wuerfel 50mm, oben rechts buendig in die ecke platte 50x50x10",
    child_dims=(50, 50, 10),
    child_text="oben rechts buendig in die ecke platte 50x50x10",
    placement_sents=["oben rechts buendig in die ecke platte 50x50x10"],
    normalized={
        "parent": "wuerfel", "seite": "oben",
        "ausrichtung": "buendig_oben_rechts", "orientierung": "standard",
        "anliegende_flaeche": "keine", "abstand": {},
        "winkel": 0, "anker": "", "pre_rotation": {}, "notes": "",
    },
    category="flush", difficulty="P2",
)

C3 = _build_trace(
    tid="c3_hochkant_flush_unten",
    spec=("wuerfel 50mm, rechts platte 100x100x20 hochkant, "
          "die 100x20 seite liegt an, untere kante buendig"),
    child_dims=(100, 100, 20),
    child_text=("rechts platte 100x100x20 hochkant, "
                "die 100x20 seite liegt an, untere kante buendig"),
    placement_sents=[
        "rechts platte 100x100x20 hochkant",
        "die 100x20 seite liegt an",
        "untere kante buendig",
    ],
    normalized={
        "parent": "wuerfel", "seite": "rechts",
        "ausrichtung": "buendig_unten", "orientierung": "hochkant",
        "anliegende_flaeche": "100x20", "abstand": {},
        "winkel": 0, "anker": "", "pre_rotation": {}, "notes": "",
    },
    category="hochkant_flush", difficulty="P3",
)

C4 = _build_trace(
    tid="c4_vorne_edge_distance",
    spec=("wuerfel 50mm, vorne platte 80x60x15, 30x80 seite liegt an, "
          "von oben 10mm versetzt"),
    child_dims=(80, 60, 15),
    child_text=("vorne platte 80x60x15, 30x80 seite liegt an, "
                "von oben 10mm versetzt"),
    placement_sents=[
        "vorne platte 80x60x15",
        "30x80 seite liegt an",
        "von oben 10mm versetzt",
    ],
    normalized={
        "parent": "wuerfel", "seite": "vorne",
        "ausrichtung": "von_kanten", "orientierung": "hochkant",
        "anliegende_flaeche": "30x80", "abstand": {"abstand_oben": 10},
        "winkel": 0, "anker": "", "pre_rotation": {}, "notes": "",
    },
    category="vorne_edge", difficulty="P3",
)

C5 = _build_trace(
    tid="c5_placement_plus_feature_split",
    spec=("wuerfel 50mm, oben drauf platte 60x60x20 zentriert, "
          "in der platte mittig eine bohrung d10 durchgehend"),
    child_dims=(60, 60, 20),
    child_text=("oben drauf platte 60x60x20 zentriert, "
                "in der platte mittig eine bohrung d10 durchgehend"),
    placement_sents=["oben drauf platte 60x60x20 zentriert"],
    feature_sents=["in der platte mittig eine bohrung d10 durchgehend"],
    normalized={
        "parent": "wuerfel", "seite": "oben",
        "ausrichtung": "zentriert", "orientierung": "standard",
        "anliegende_flaeche": "keine", "abstand": {},
        "winkel": 0, "anker": "", "pre_rotation": {}, "notes": "",
    },
    aktionen=[{
        "teil_id": "platte", "seite": "oben",
        "beschreibung": "in der platte mittig eine bohrung d10 durchgehend",
    }],
    normalizer_pairs=[{
        "input": {
            "beschreibung": "in der platte mittig eine bohrung d10 durchgehend",
            "seite": "oben",
            "teil_type": "box",
            "teil_params": {"x": 60, "y": 60, "z": 20},
            "specification": "in der platte mittig eine bohrung d10 durchgehend",
        },
        "output": {
            "type": "hole",
            "params": {"d": 10, "depth": "through"},
            "position": {"side": "oben", "alignment": "centered"},
            "operation": "subtract",
        },
    }],
    category="mixed_split", difficulty="P3",
)

C6 = _build_trace(
    tid="c6_only_rotation_no_offsets",
    spec="wuerfel 50mm, oben drauf platte 100x40x20, um 45 grad gedreht",
    child_dims=(100, 40, 20),
    child_text="oben drauf platte 100x40x20, um 45 grad gedreht",
    placement_sents=[
        "oben drauf platte 100x40x20",
        "um 45 grad gedreht",
    ],
    normalized={
        "parent": "wuerfel", "seite": "oben",
        "ausrichtung": "zentriert", "orientierung": "standard",
        "anliegende_flaeche": "keine", "abstand": {},
        "winkel": 45.0, "anker": "", "pre_rotation": {}, "notes": "",
    },
    category="rotation_only", difficulty="P2",
)

C7 = _build_trace(
    tid="c7_pre_rotation_3d",
    spec=("wuerfel 50mm, rechts platte 40x40x20, "
          "in x-achse um 90 grad gekippt, anschliessend zentriert anliegend"),
    child_dims=(40, 40, 20),
    child_text=("rechts platte 40x40x20, "
                "in x-achse um 90 grad gekippt, anschliessend zentriert anliegend"),
    placement_sents=[
        "rechts platte 40x40x20",
        "in x-achse um 90 grad gekippt",
        "anschliessend zentriert anliegend",
    ],
    normalized={
        "parent": "wuerfel", "seite": "rechts",
        "ausrichtung": "zentriert", "orientierung": "standard",
        "anliegende_flaeche": "keine", "abstand": {},
        "winkel": 0, "anker": "",
        "pre_rotation": {"x": 90},
        "notes": "3d kippung vor anlage",
    },
    category="pre_rotation", difficulty="P4",
)


# ─────────────────────────────────────────────────────────────────────
# NACH-AUSSEN-CASES (N1-N3) — Bezugskante/Ecke + Versatz
# ─────────────────────────────────────────────────────────────────────

N1 = _build_trace(
    tid="n1_outward_edge_overhang",
    spec=("wuerfel 50mm, oben drauf platte 60x60x10, "
          "an der rechten kante 10mm nach aussen versetzt"),
    child_dims=(60, 60, 10),
    child_text=("oben drauf platte 60x60x10, "
                "an der rechten kante 10mm nach aussen versetzt"),
    placement_sents=[
        "oben drauf platte 60x60x10",
        "an der rechten kante 10mm nach aussen versetzt",
    ],
    normalized={
        "parent": "wuerfel", "seite": "oben",
        "ausrichtung": "buendig_rechts", "orientierung": "standard",
        "anliegende_flaeche": "keine",
        "abstand": {"versatz_rechts": 10},
        "winkel": 0, "anker": "", "pre_rotation": {},
        "notes": "ueberhang nach rechts ueber buendig hinaus",
    },
    category="outward_edge", difficulty="P4",
)

N2 = _build_trace(
    tid="n2_outward_corner_diagonal",
    spec=("wuerfel 50mm, oben drauf platte 50x50x15, "
          "obere rechte ecke 5mm nach aussen versetzt"),
    child_dims=(50, 50, 15),
    child_text=("oben drauf platte 50x50x15, "
                "obere rechte ecke 5mm nach aussen versetzt"),
    placement_sents=[
        "oben drauf platte 50x50x15",
        "obere rechte ecke 5mm nach aussen versetzt",
    ],
    normalized={
        "parent": "wuerfel", "seite": "oben",
        "ausrichtung": "buendig_oben_rechts", "orientierung": "standard",
        "anliegende_flaeche": "keine",
        "abstand": {"versatz_rechts": 5, "versatz_oben": 5},
        "winkel": 0,
        "anker": "top_right_auf_top_right",
        "pre_rotation": {},
        "notes": "diagonal-ueberhang in obere rechte ecke",
    },
    category="outward_corner", difficulty="P4",
)

N3 = _build_trace(
    tid="n3_overhang_synonym",
    spec=("wuerfel 50mm, oben drauf platte 80x80x10, "
          "rechte kante mit 15mm ueberstand"),
    child_dims=(80, 80, 10),
    child_text=("oben drauf platte 80x80x10, "
                "rechte kante mit 15mm ueberstand"),
    placement_sents=[
        "oben drauf platte 80x80x10",
        "rechte kante mit 15mm ueberstand",
    ],
    normalized={
        "parent": "wuerfel", "seite": "oben",
        "ausrichtung": "buendig_rechts", "orientierung": "standard",
        "anliegende_flaeche": "keine",
        "abstand": {"versatz_rechts": 15},
        "winkel": 0, "anker": "", "pre_rotation": {},
        "notes": "synonym: ueberstand = nach aussen versetzt",
    },
    category="outward_synonym", difficulty="P3",
)


# ─────────────────────────────────────────────────────────────────────
# POCKET-CASES (P1-P4) — gleicher Anker-Wortschatz, operation=subtract
# ─────────────────────────────────────────────────────────────────────
# Pockets durchlaufen den NormalizerAgent (im feature_definierer-Node), nicht
# den platzierer. Schemafelder im Output-Feature: position {side, alignment,
# edge_distances/versatz, anchor, angle_deg}. Single-part traces — wuerfel
# als Parent, Pocket als Aktion.

def _pocket_trace(*, tid, basis_size, pocket_dims, action_text, feature,
                  category, difficulty="P3"):
    basis = _wuerfel(basis_size)
    aktion = {
        "teil_id": "wuerfel", "seite": "oben",
        "beschreibung": action_text,
    }
    return {
        "id": tid,
        "specification": f"wuerfel {basis_size}mm, {action_text}",
        "metadata": {"category": category, "difficulty": difficulty,
                     "sprachstil": "natuerlich"},
        "inventar": {
            "teil_count": 1,
            "teile": [basis],
            "aktionen": [aktion],
        },
        "teil_texte": {
            "wuerfel": f"{basis_size}mm wuerfel, {action_text}",
        },
        # Single-part: position_extractor laeuft mit features-only Labels
        "position_extractor": {
            "positionen": [{
                "teil_id": "wuerfel", "is_root": True,
                "placement_sentences": [],
                "feature_sentences": [action_text],
            }],
        },
        "position_normalizer": [],
        "normalizer_pairs": [{
            "input": {
                "beschreibung": action_text,
                "seite": "oben",
                "teil_type": "box",
                "teil_params": {"x": basis_size, "y": basis_size, "z": basis_size},
                "specification": action_text,
            },
            "output": feature,
        }],
    }


P1 = _pocket_trace(
    tid="p1_pocket_centered_trivial",
    basis_size=80, pocket_dims=(30, 30, 10),
    action_text="oben mittig eine tasche 30x30x10",
    feature={
        "type": "pocket_rect",
        "params": {"x": 30, "y": 30, "depth": 10},
        "position": {"side": "oben", "alignment": "centered",
                     "edge_distances": None, "angle_deg": 0, "notes": ""},
        "operation": "subtract",
    },
    category="pocket_trivial", difficulty="P2",
)

P2 = _pocket_trace(
    tid="p2_pocket_anchor_corner",
    basis_size=80, pocket_dims=(20, 20, 8),
    action_text=("oben rechts eine tasche 20x20x8, obere rechte ecke der tasche "
                 "von oberer rechter ecke jeweils 10mm entfernt"),
    feature={
        "type": "pocket_rect",
        "params": {"x": 20, "y": 20, "depth": 8},
        "position": {
            "side": "oben",
            "alignment": "centered",
            "edge_distances": {"right": 10, "top": 10},
            "anchor": {"child_point": "top_right", "parent_point": "top_right"},
            "angle_deg": 0, "notes": "anker corner-corner",
        },
        "operation": "subtract",
    },
    category="pocket_anchor_corner", difficulty="P5",
)

P3 = _pocket_trace(
    tid="p3_pocket_edge_midpoint",
    basis_size=100, pocket_dims=(40, 20, 5),
    action_text=("oben eine tasche 40x20x5, "
                 "von links 15mm und von oben 25mm entfernt"),
    feature={
        "type": "pocket_rect",
        "params": {"x": 40, "y": 20, "depth": 5},
        "position": {
            "side": "oben",
            "alignment": "von_kanten",
            "edge_distances": {"left": 15, "top": 25},
            "angle_deg": 0, "notes": "center der tasche aus kanten gemessen",
        },
        "operation": "subtract",
    },
    category="pocket_edge_distance", difficulty="P3",
)

P4 = _pocket_trace(
    tid="p4_pocket_rotated_centered",
    basis_size=80, pocket_dims=(25, 25, 10),
    action_text="oben mittig eine tasche 25x25x10, um 30 grad gedreht",
    feature={
        "type": "pocket_rect",
        "params": {"x": 25, "y": 25, "depth": 10},
        "position": {
            "side": "oben", "alignment": "centered",
            "edge_distances": None, "angle_deg": 30.0, "notes": "",
        },
        "operation": "subtract",
    },
    category="pocket_rotation", difficulty="P3",
)


ALL_TRACES = [U1, U2, U3, U4, U5, U6, U7,
              C1, C2, C3, C4, C5, C6, C7,
              N1, N2, N3,
              P1, P2, P3, P4]


def build() -> list[dict]:
    return ALL_TRACES


if __name__ == "__main__":
    json.dump(ALL_TRACES, sys.stdout, indent=2, ensure_ascii=False)
