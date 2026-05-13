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


def _bp_slot(position_extras: dict, slot_size=(5, 3, 40), angle_deg=90.0) -> dict:
    """120x90x50 Wuerfel mit Nut oben — Breite/Tiefe/Laenge bleiben getrennt."""
    width, depth, length = slot_size
    position = {
        "side": "oben", "alignment": "centered",
        "edge_distances": None, "angle_deg": angle_deg, "notes": "entlang Y",
    }
    position.update(position_extras)
    return {
        "build_order": ["wuerfel", "nut"],
        "features": {
            "wuerfel": {
                "id": "wuerfel", "type": "box",
                "params": {"x": 120, "y": 90, "z": 50},
                "orientation": "standard",
                "parent": None, "operation": "add",
            },
            "nut": {
                "id": "nut", "type": "slot",
                "params": {"width": width, "depth": depth, "length": length},
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


def test_kante_top_left_on_y_slot_uses_width_and_length():
    """Run adbf823d: Nut 5x3, laenge=40 entlang Y, kante_oben=18 +
    kante_links=12. Die Nut darf nicht bei der oberen Kante starten:
    X-Span -48..-43, Y-Span -13..27."""
    bp = _bp_slot({
        "edge_distances": {"top": 18, "left": 12},
        "pocket_edge_distances": {"top": 18, "left": 12},
    })
    res = resolve_blueprint(bp)
    p = res["features"]["nut"]["placement"]
    assert p["offset_x"] == -45.5
    assert p["offset_y"] == 7.0


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


# ── Side-Faces: kante_* darf NICHT durch fehlendes z-Param gebrochen werden
# (Run e3ddd2d0 Bug 2: tasche_vorne_5 / tasche_links_10 / tasche_rechts_18
# alle 15mm zu hoch weil _get_child_face_size cz=0 las.) ─────────────


def _bp_pocket_on_side(side: str, position_extras: dict,
                       pocket_size=(20, 30, 10)) -> dict:
    """200x200x200 Wuerfel mit Tasche auf side ∈ {vorne, links, rechts, hinten}."""
    px, py, pz = pocket_size
    position = {
        "side": side, "alignment": "centered",
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


def test_kante_top_left_on_vorne_face_uses_pocket_y_as_height():
    """Run e3ddd2d0 tasche_vorne_5: 20x30 Pocket auf <Y, kante_oben=10 +
    kante_links=10. Erwartung wie auf >Z: Center (-80, +75). Vorher fiel
    der Resolver auf cz=0 zurueck und lieferte (-75, +90)."""
    bp = _bp_pocket_on_side(
        "vorne",
        {"pocket_edge_distances": {"top": 10, "left": 10}},
        pocket_size=(20, 30, 10),
    )
    res = resolve_blueprint(bp)
    p = res["features"]["tasche"]["placement"]
    assert p["offset_x"] == -80.0
    assert p["offset_y"] == 75.0


def test_kante_top_left_on_links_face_uses_pocket_y_as_height():
    """Run e3ddd2d0 tasche_links_10: identisch zu vorne_5 aber face <X."""
    bp = _bp_pocket_on_side(
        "links",
        {"pocket_edge_distances": {"top": 10, "left": 10}},
        pocket_size=(20, 30, 10),
    )
    res = resolve_blueprint(bp)
    p = res["features"]["tasche"]["placement"]
    assert p["offset_x"] == -80.0
    assert p["offset_y"] == 75.0


def test_kante_top_left_on_rechts_face_uses_pocket_y_as_height():
    """Run e3ddd2d0 tasche_rechts_18: identisch aber face >X."""
    bp = _bp_pocket_on_side(
        "rechts",
        {"pocket_edge_distances": {"top": 10, "left": 10}},
        pocket_size=(20, 30, 10),
    )
    res = resolve_blueprint(bp)
    p = res["features"]["tasche"]["placement"]
    assert p["offset_x"] == -80.0
    assert p["offset_y"] == 75.0


def test_center_offset_adds_on_top_of_abstand():
    """Bug 4 (Run e3ddd2d0 tasche_rechts_22): User-Phrase
    "von der rechten Seite 25mm entfernt ... 10mm nach rechts versetzt"
    erzeugt edge_distances={right:25} UND center_offset={right:10}.
    Erwartung: edge legt Basis (ox=+75), center_offset addiert (+10) → ox=85.
    Vorher: center_offset ignoriert → ox=75."""
    bp = _bp_pocket({
        "edge_distances": {"right": 25},
        "center_offset": {"right": 10},
    }, pocket_size=(40, 40, 10))
    res = resolve_blueprint(bp)
    p = res["features"]["tasche"]["placement"]
    assert p["offset_x"] == 85.0


def test_center_offset_adds_on_top_of_kante():
    """Same composition but with pocket_edge_distances (kante_*).
    Pocket-Edge bei +75 → Center +55, plus 10mm versetzt → Center +65."""
    bp = _bp_pocket({
        "pocket_edge_distances": {"right": 25},
        "center_offset": {"right": 10},
    }, pocket_size=(40, 40, 10))
    res = resolve_blueprint(bp)
    p = res["features"]["tasche"]["placement"]
    assert p["offset_x"] == 65.0


def test_center_offset_alone_still_works():
    """Regression: center_offset OHNE edge_distances/pocket_edge_distances
    bleibt eigenstaendig (Versatz von der Mitte)."""
    bp = _bp_pocket({"center_offset": {"right": 20, "top": 30}},
                    pocket_size=(40, 40, 10))
    res = resolve_blueprint(bp)
    p = res["features"]["tasche"]["placement"]
    assert p["offset_x"] == 20.0
    assert p["offset_y"] == 30.0


def test_center_offset_added_axis_independently():
    """Mischform: edge auf X-Achse, center_offset NUR auf Y-Achse.
    X = pure edge (ox=75), Y = pure center (oy=30 von der Mitte)."""
    bp = _bp_pocket({
        "edge_distances": {"right": 25},
        "center_offset": {"top": 30},
    }, pocket_size=(40, 40, 10))
    res = resolve_blueprint(bp)
    p = res["features"]["tasche"]["placement"]
    assert p["offset_x"] == 75.0
    assert p["offset_y"] == 30.0


def test_box_child_on_side_face_keeps_world_axis_remap():
    """Regression: 3D-Box (Platte mit z-Param) muss weiterhin pro Face
    remappen — sonst landet Anchor-Berechnung fuer additive Kinder im Eimer."""
    bp = {
        "build_order": ["wuerfel", "platte"],
        "features": {
            "wuerfel": {
                "id": "wuerfel", "type": "box",
                "params": {"x": 200, "y": 200, "z": 200},
                "orientation": "standard",
                "parent": None, "operation": "add",
            },
            "platte": {
                "id": "platte", "type": "box",
                "params": {"x": 140, "y": 40, "z": 20},  # 3D box, z is set
                "orientation": "standard",
                "parent": "wuerfel", "operation": "add",
                "position": {
                    "side": "vorne",
                    "alignment": "flush_right",
                    "edge_distances": None,
                    "angle_deg": 0.0, "notes": "",
                },
            },
        },
    }
    res = resolve_blueprint(bp)
    p = res["features"]["platte"]["placement"]
    # On <Y: child_w=cx=140, child_h=cz=20. flush_right → ox = +(200-140)/2 = 30.
    assert p["offset_x"] == 30.0
