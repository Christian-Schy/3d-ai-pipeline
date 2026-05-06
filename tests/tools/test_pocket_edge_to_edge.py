"""tests/tools/test_pocket_edge_to_edge.py

Regression: ADR 0003 Stufe 5c, Bug 6 (gefunden in Run fc2b3b45).
Pocket_rect / slot / cutout / groove folgen edge-to-edge — bei
"Tasche 25mm von rechter Kante" liegt die rechte Kante der Tasche
25mm von der rechten Kante des Wuerfels, NICHT die Mitte der Tasche.
Holes folgen weiter edge-to-center, weil sie keinen rechteckigen
Extent in der Face-Ebene haben.
"""
from __future__ import annotations

from src.tools.blueprint_resolver import resolve_blueprint


def _bp_with_pocket(edge_distances: dict, pocket_size=(60, 40, 10)) -> dict:
    """200x200x200 Wuerfel mit einer Tasche oben an der gegebenen edge_distance."""
    px, py, pz = pocket_size
    return {
        "build_order": ["wuerfel", "tasche"],
        "features": {
            "wuerfel": {
                "id": "wuerfel", "type": "box",
                "params": {"x": 200, "y": 200, "z": 200},
                "orientation": "standard",
                "parent": None, "operation": "add",
            },
            "tasche": {
                "id": "tasche", "type": "pocket_rect",
                "params": {"x": px, "y": py, "depth": pz},
                "orientation": "standard",
                "parent": "wuerfel", "operation": "subtract",
                "position": {
                    "side": "oben", "alignment": "centered",
                    "edge_distances": edge_distances,
                    "angle_deg": 0.0, "notes": "von_kanten",
                },
            },
        },
    }


def _bp_with_hole(edge_distances: dict, diameter: float = 10) -> dict:
    return {
        "build_order": ["wuerfel", "bohrung"],
        "features": {
            "wuerfel": {
                "id": "wuerfel", "type": "box",
                "params": {"x": 200, "y": 200, "z": 200},
                "orientation": "standard",
                "parent": None, "operation": "add",
            },
            "bohrung": {
                "id": "bohrung", "type": "hole_single",
                "params": {"diameter": diameter, "depth": 10},
                "orientation": "standard",
                "parent": "wuerfel", "operation": "subtract",
                "position": {
                    "side": "oben", "alignment": "centered",
                    "edge_distances": edge_distances,
                    "angle_deg": 0.0, "notes": "von_kanten",
                },
            },
        },
    }


# ── Pocket: edge-to-edge ─────────────────────────────────────────────────


def test_pocket_right_25_lands_pocket_right_edge_at_75():
    """Tasche 40x40, abstand_rechts=25 → rechte Kante bei +75 (=100-25),
    Mitte ox=+55."""
    bp = _bp_with_pocket({"right": 25}, pocket_size=(40, 40, 10))
    res = resolve_blueprint(bp)
    place = res["features"]["tasche"]["placement"]
    assert place["offset_x"] == 55.0
    # Rechte Pocket-Kante = ox + x/2 = 55 + 20 = 75 = (face_half - 25). ✓


def test_pocket_top_30_lands_pocket_top_edge_at_70():
    """Tasche 60x40, abstand_oben=30 → obere Kante bei +70 (=100-30),
    Mitte oy=+50."""
    bp = _bp_with_pocket({"top": 30}, pocket_size=(60, 40, 10))
    res = resolve_blueprint(bp)
    place = res["features"]["tasche"]["placement"]
    assert place["offset_y"] == 50.0


def test_pocket_top_left_20x30_corner_placement():
    """Tasche 20x30, abstand_oben=10 + abstand_links=10 →
    obere Kante bei +90, linke Kante bei -90.
    Mitte ox=-90+10=-80, oy=+90-15=+75."""
    bp = _bp_with_pocket({"top": 10, "left": 10}, pocket_size=(20, 30, 10))
    res = resolve_blueprint(bp)
    place = res["features"]["tasche"]["placement"]
    assert place["offset_x"] == -80.0
    assert place["offset_y"] == 75.0


def test_pocket_with_zero_distance_sits_flush_to_edge():
    """abstand_rechts=0.5 → Pocket-Right-Edge = +99.5, sehr nah am Rand."""
    bp = _bp_with_pocket({"right": 0.5}, pocket_size=(20, 20, 10))
    res = resolve_blueprint(bp)
    place = res["features"]["tasche"]["placement"]
    assert place["offset_x"] == 89.5  # 100 - 0.5 - 10 = 89.5


# ── Hole: edge-to-center (unveraendert) ─────────────────────────────────


def test_hole_right_25_lands_hole_center_at_75():
    """Bohrung 10mm, abstand_rechts=25 → CENTER bei +75 (Hole-Konvention)."""
    bp = _bp_with_hole({"right": 25})
    res = resolve_blueprint(bp)
    place = res["features"]["bohrung"]["placement"]
    assert place["offset_x"] == 75.0


def test_hole_top_left_corner_5mm():
    """Bohrung mit abstand_oben=5 + abstand_links=5 → Hole-Mitte bei
    (-95, +95) — knapp 5mm zum Rand der 200x200-Flaeche."""
    bp = _bp_with_hole({"top": 5, "left": 5}, diameter=8)
    res = resolve_blueprint(bp)
    place = res["features"]["bohrung"]["placement"]
    assert place["offset_x"] == -95.0
    assert place["offset_y"] == 95.0
