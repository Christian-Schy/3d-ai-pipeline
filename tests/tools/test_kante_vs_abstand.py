"""tests/tools/test_kante_vs_abstand.py

Konvention nach User-Vorgabe (Stufe 5c, ADR 0003):

  abstand_<dir>  (DEFAULT)  → Feature-CENTER X mm von Parent-Edge.
                              Triggered by: "von der oberen Kante 10mm
                              entfernt" / "von rechts 25mm entfernt".
  kante_<dir>    (EXPLICIT) → Feature-EDGE X mm von Parent-Edge.
                              Triggered by: "die obere Kante der Tasche
                              von oben 10mm entfernt" / "untere Seite
                              der Tasche von unten 20mm entfernt"
                              (BEIDE Kanten benannt).

Bohrungen sind point-like; nur abstand_* hat semantischen Sinn.
Pockets/slots/cutouts/grooves haben rechteckigen Extent und unterstuetzen
beide Konventionen — die Klassifizierer-Wahl haengt am Phrasing.
Pro Achse: nur EINE Konvention; Mischformen ueber zwei Achsen erlaubt.
"""
from __future__ import annotations

from src.tools.blueprint_resolver import resolve_blueprint


def _bp_pocket(position_extras: dict, pocket_size=(40, 40, 10)) -> dict:
    """200x200x200 Wuerfel mit Tasche oben — Position-Felder injizierbar."""
    px, py, pz = pocket_size
    position = {
        "side": "oben", "alignment": "centered",
        "edge_distances": None, "angle_deg": 0.0, "notes": "",
    }
    position.update(position_extras)
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
                "position": position,
            },
        },
    }


# ── DEFAULT abstand_* (edge-to-CENTER) ─────────────────────────────


def test_abstand_rechts_25_keeps_pocket_center_at_75():
    """40x40 Tasche, abstand_rechts=25 → Center 25mm von Cube-Rand →
    ox=+75, Pocket-Right-Edge bei +95 (5mm Cube-Rand-Gap)."""
    bp = _bp_pocket({"edge_distances": {"right": 25}})
    res = resolve_blueprint(bp)
    assert res["features"]["tasche"]["placement"]["offset_x"] == 75.0


def test_abstand_oben_30_keeps_pocket_center_at_70():
    bp = _bp_pocket({"edge_distances": {"top": 30}}, pocket_size=(60, 40, 10))
    res = resolve_blueprint(bp)
    assert res["features"]["tasche"]["placement"]["offset_y"] == 70.0


# ── EXPLICIT kante_* (edge-to-EDGE) ────────────────────────────────


def test_kante_rechts_25_pushes_pocket_edge_to_75():
    """40x40 Tasche, kante_rechts=25 → Pocket-Right-Edge bei +75
    → Center bei +55."""
    bp = _bp_pocket({"pocket_edge_distances": {"right": 25}})
    res = resolve_blueprint(bp)
    assert res["features"]["tasche"]["placement"]["offset_x"] == 55.0


def test_kante_top_30_pushes_pocket_top_edge_to_70():
    """60x40 Tasche, kante_oben=30 → Pocket-Top bei +70 → Center +50."""
    bp = _bp_pocket({"pocket_edge_distances": {"top": 30}},
                    pocket_size=(60, 40, 10))
    res = resolve_blueprint(bp)
    assert res["features"]["tasche"]["placement"]["offset_y"] == 50.0


def test_kante_corner_top_left():
    """20x30 Tasche, kante_oben=10 + kante_links=10 → Pocket-Top bei +90,
    Pocket-Left bei -90 → Center (-80, +75)."""
    bp = _bp_pocket(
        {"pocket_edge_distances": {"top": 10, "left": 10}},
        pocket_size=(20, 30, 10),
    )
    res = resolve_blueprint(bp)
    p = res["features"]["tasche"]["placement"]
    assert p["offset_x"] == -80.0
    assert p["offset_y"] == 75.0


# ── Mischformen: pro Achse die richtige Konvention ─────────────────


def test_mixed_kante_x_with_abstand_y():
    """40x40 Tasche, kante_links=10 (edge-to-edge) + abstand_oben=30
    (edge-to-center). Pocket-Left bei -90 → Center ox=-70.
    Center oy=+70."""
    bp = _bp_pocket({
        "pocket_edge_distances": {"left": 10},
        "edge_distances": {"top": 30},
    }, pocket_size=(40, 40, 10))
    res = resolve_blueprint(bp)
    p = res["features"]["tasche"]["placement"]
    assert p["offset_x"] == -70.0
    assert p["offset_y"] == 70.0


def test_kante_overrides_abstand_on_same_axis():
    """Wenn der LLM beides emittiert (sollte er nicht), gewinnt kante_*
    auf derselben Achse — defensives Verhalten."""
    bp = _bp_pocket({
        "pocket_edge_distances": {"right": 25},
        "edge_distances": {"right": 25},  # would put center at 75, ignored
    }, pocket_size=(40, 40, 10))
    res = resolve_blueprint(bp)
    assert res["features"]["tasche"]["placement"]["offset_x"] == 55.0
