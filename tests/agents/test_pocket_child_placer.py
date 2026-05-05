"""tests/agents/test_pocket_child_placer.py — Unit tests for PocketChildPlacer.

Kernverhalten (V2):
  - LLM bekommt nur die Mapping-Aufgabe (welche Bohrung -> welche Tasche?)
  - Position vom Upstream-Feature wird 1:1 durchgereicht (insbesondere
    center_offset / edge_distances).
  - depth_reference wird deterministisch auf "pocket_floor" gesetzt.
  - IDs werden zu hole_in_<pocket>_<idx> umbenannt.

Regression: Run 965da548 hatte den Bug, dass das LLM die Position erneut
parste und dabei "10mm nach oben" verlor. Der erste Test deckt das ab.
"""

from unittest.mock import MagicMock


def _make_agent():
    from src.agents.pocket_child_placer import PocketChildPlacer
    return PocketChildPlacer()


def _mock_call_json(agent, return_value):
    agent.call_json = MagicMock(return_value=return_value)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _bp_one_pocket_with_hole(hole_position: dict) -> dict:
    """Blueprint mit einem Wuerfel, einer Tasche obenauf und einer Bohrung,
    deren Position der Upstream-Agent bereits korrekt extrahiert hat."""
    return {
        "build_order": ["wuerfel", "tasche_oben_0", "bohrung_oben_1"],
        "features": {
            "wuerfel": {
                "id": "wuerfel", "type": "box",
                "params": {"x": 200, "y": 200, "z": 200},
                "parent": None, "operation": "add",
            },
            "tasche_oben_0": {
                "id": "tasche_oben_0", "type": "pocket_rect",
                "params": {"x": 60, "y": 40, "depth": 10},
                "parent": "wuerfel", "operation": "subtract",
                "position": {"side": "oben", "alignment": "centered",
                             "edge_distances": {"top": 30, "right": 40},
                             "angle_deg": 10.0},
            },
            "bohrung_oben_1": {
                "id": "bohrung_oben_1", "type": "hole_single",
                "params": {"diameter": 10, "depth": 10},
                "parent": "wuerfel", "operation": "subtract",
                "position": hole_position,
                "notes": "in der tasche um 15mm nach rechts versetzt und um 10mm nach oben",
            },
        },
    }


# ── Tests ────────────────────────────────────────────────────────────────────

class TestPositionPassthrough:
    """Position vom Upstream-Feature darf nicht neu geparst werden."""

    def test_center_offset_passes_through_unchanged(self):
        """Run 965da548 regression: center_offset {top:10, right:15} muss
        nach dem Re-Parent IDENTISCH erhalten bleiben."""
        agent = _make_agent()
        upstream_pos = {
            "side": "oben", "alignment": "centered",
            "edge_distances": None, "angle_deg": 0.0,
            "notes": "von_mitte",
            "center_offset": {"top": 10, "right": 15},
        }
        bp = _bp_one_pocket_with_hole(upstream_pos)
        _mock_call_json(agent, {
            "assignments": [
                {"hole_feature_id": "bohrung_oben_1",
                 "pocket_id": "tasche_oben_0"},
            ]
        })

        result = agent.extract(
            "Wuerfel mit Tasche, in der tasche eine Bohrung 15 nach rechts und 10 nach oben",
            bp,
        )

        assert "features_to_add" in result
        assert len(result["features_to_add"]) == 1
        new_feat = next(iter(result["features_to_add"].values()))
        # Beide Achsen muessen ueberleben.
        assert new_feat["position"]["center_offset"] == {"top": 10, "right": 15}
        # Auch die anderen Position-Felder bleiben gleich.
        assert new_feat["position"]["side"] == "oben"
        assert new_feat["position"]["alignment"] == "centered"

    def test_edge_distances_pass_through(self):
        agent = _make_agent()
        upstream_pos = {
            "side": "oben", "alignment": "centered",
            "edge_distances": {"top": 5, "left": 5},
            "angle_deg": 0.0, "notes": "oben-links",
        }
        bp = _bp_one_pocket_with_hole(upstream_pos)
        _mock_call_json(agent, {
            "assignments": [{"hole_feature_id": "bohrung_oben_1",
                             "pocket_id": "tasche_oben_0"}]
        })
        result = agent.extract(
            "Wuerfel mit Tasche, in der tasche eine Bohrung oben links 5mm",
            bp,
        )
        new_feat = next(iter(result["features_to_add"].values()))
        assert new_feat["position"]["edge_distances"] == {"top": 5, "left": 5}

    def test_depth_reference_set_to_pocket_floor(self):
        """depth_reference wird deterministisch ueberschrieben — egal was
        upstream stand."""
        agent = _make_agent()
        upstream_pos = {"side": "oben", "alignment": "centered",
                        "depth_reference": "face"}
        bp = _bp_one_pocket_with_hole(upstream_pos)
        _mock_call_json(agent, {
            "assignments": [{"hole_feature_id": "bohrung_oben_1",
                             "pocket_id": "tasche_oben_0"}]
        })
        result = agent.extract("in der tasche bohrung", bp)
        new_feat = next(iter(result["features_to_add"].values()))
        assert new_feat["position"]["depth_reference"] == "pocket_floor"

    def test_params_preserved(self):
        agent = _make_agent()
        bp = _bp_one_pocket_with_hole({"side": "oben", "alignment": "centered"})
        _mock_call_json(agent, {
            "assignments": [{"hole_feature_id": "bohrung_oben_1",
                             "pocket_id": "tasche_oben_0"}]
        })
        result = agent.extract("in der tasche bohrung", bp)
        new_feat = next(iter(result["features_to_add"].values()))
        assert new_feat["params"] == {"diameter": 10, "depth": 10}
        assert new_feat["parent"] == "tasche_oben_0"
        assert new_feat["operation"] == "subtract"


class TestIDRenaming:
    def test_new_id_follows_convention(self):
        agent = _make_agent()
        bp = _bp_one_pocket_with_hole({"side": "oben", "alignment": "centered"})
        _mock_call_json(agent, {
            "assignments": [{"hole_feature_id": "bohrung_oben_1",
                             "pocket_id": "tasche_oben_0"}]
        })
        result = agent.extract("in der tasche bohrung", bp)
        new_id = next(iter(result["features_to_add"].keys()))
        assert new_id == "hole_in_tasche_oben_0_1"

    def test_multiple_holes_per_pocket_get_increasing_index(self):
        agent = _make_agent()
        bp = _bp_one_pocket_with_hole({"side": "oben", "alignment": "centered"})
        # Add a second upstream hole on the part.
        bp["features"]["bohrung_oben_2"] = {
            "id": "bohrung_oben_2", "type": "hole_single",
            "params": {"diameter": 8, "depth": 10},
            "parent": "wuerfel", "operation": "subtract",
            "position": {"side": "oben", "alignment": "centered",
                         "edge_distances": {"left": 10, "top": 10}},
            "notes": "zweite bohrung in der tasche",
        }
        bp["build_order"].append("bohrung_oben_2")
        _mock_call_json(agent, {
            "assignments": [
                {"hole_feature_id": "bohrung_oben_1", "pocket_id": "tasche_oben_0"},
                {"hole_feature_id": "bohrung_oben_2", "pocket_id": "tasche_oben_0"},
            ]
        })
        result = agent.extract("in der tasche zwei bohrungen", bp)
        new_ids = sorted(result["features_to_add"].keys())
        assert new_ids == ["hole_in_tasche_oben_0_1", "hole_in_tasche_oben_0_2"]

    def test_originals_marked_for_removal(self):
        agent = _make_agent()
        bp = _bp_one_pocket_with_hole({"side": "oben", "alignment": "centered"})
        _mock_call_json(agent, {
            "assignments": [{"hole_feature_id": "bohrung_oben_1",
                             "pocket_id": "tasche_oben_0"}]
        })
        result = agent.extract("in der tasche bohrung", bp)
        assert result["feature_ids_to_remove"] == ["bohrung_oben_1"]


class TestSkipBehavior:
    def test_skip_when_no_in_pocket_phrase(self):
        agent = _make_agent()
        bp = _bp_one_pocket_with_hole({"side": "oben", "alignment": "centered"})
        # Sentinel: would crash if the LLM was actually invoked.
        agent.call_json = MagicMock(side_effect=AssertionError("LLM should not be called"))
        result = agent.extract("Wuerfel mit Tasche und einer Bohrung obenauf", bp)
        assert result == {}

    def test_skip_when_no_pocket(self):
        agent = _make_agent()
        bp = {
            "build_order": ["wuerfel", "bohrung_oben_1"],
            "features": {
                "wuerfel": {"id": "wuerfel", "type": "box",
                             "params": {"x": 100, "y": 100, "z": 100},
                             "parent": None, "operation": "add"},
                "bohrung_oben_1": {"id": "bohrung_oben_1", "type": "hole_single",
                                    "params": {"diameter": 10, "depth": 10},
                                    "parent": "wuerfel", "operation": "subtract",
                                    "position": {"side": "oben", "alignment": "centered"}},
            },
        }
        agent.call_json = MagicMock(side_effect=AssertionError("LLM should not be called"))
        result = agent.extract("in der tasche eine bohrung", bp)
        assert result == {}

    def test_skip_when_no_assignable_holes(self):
        agent = _make_agent()
        # Only a pocket, no upstream hole feature.
        bp = {
            "build_order": ["wuerfel", "tasche_oben_0"],
            "features": {
                "wuerfel": {"id": "wuerfel", "type": "box",
                             "params": {"x": 200, "y": 200, "z": 200},
                             "parent": None, "operation": "add"},
                "tasche_oben_0": {"id": "tasche_oben_0", "type": "pocket_rect",
                                    "params": {"x": 60, "y": 40, "depth": 10},
                                    "parent": "wuerfel", "operation": "subtract",
                                    "position": {"side": "oben", "alignment": "centered"}},
            },
        }
        agent.call_json = MagicMock(side_effect=AssertionError("LLM should not be called"))
        result = agent.extract("in der tasche eine bohrung", bp)
        assert result == {}

    def test_skip_holes_already_assigned_to_pocket(self):
        """Eine Bohrung mit parent=pocket darf nicht erneut zugeordnet werden."""
        agent = _make_agent()
        bp = {
            "build_order": ["wuerfel", "tasche_oben_0", "hole_in_tasche_oben_0_1"],
            "features": {
                "wuerfel": {"id": "wuerfel", "type": "box",
                             "params": {"x": 200, "y": 200, "z": 200},
                             "parent": None, "operation": "add"},
                "tasche_oben_0": {"id": "tasche_oben_0", "type": "pocket_rect",
                                    "params": {"x": 60, "y": 40, "depth": 10},
                                    "parent": "wuerfel", "operation": "subtract",
                                    "position": {"side": "oben", "alignment": "centered"}},
                "hole_in_tasche_oben_0_1": {
                    "id": "hole_in_tasche_oben_0_1", "type": "hole_single",
                    "params": {"diameter": 10, "depth": 10},
                    "parent": "tasche_oben_0", "operation": "subtract",
                    "position": {"side": "oben", "alignment": "centered",
                                  "depth_reference": "pocket_floor"},
                },
            },
        }
        agent.call_json = MagicMock(side_effect=AssertionError("LLM should not be called"))
        result = agent.extract("in der tasche eine bohrung", bp)
        assert result == {}


class TestValidation:
    def test_unknown_hole_id_dropped(self):
        agent = _make_agent()
        bp = _bp_one_pocket_with_hole({"side": "oben", "alignment": "centered"})
        _mock_call_json(agent, {
            "assignments": [
                {"hole_feature_id": "ghost_hole", "pocket_id": "tasche_oben_0"},
            ]
        })
        result = agent.extract("in der tasche bohrung", bp)
        assert result == {}

    def test_unknown_pocket_id_dropped(self):
        agent = _make_agent()
        bp = _bp_one_pocket_with_hole({"side": "oben", "alignment": "centered"})
        _mock_call_json(agent, {
            "assignments": [
                {"hole_feature_id": "bohrung_oben_1", "pocket_id": "ghost_pocket"},
            ]
        })
        result = agent.extract("in der tasche bohrung", bp)
        assert result == {}

    def test_duplicate_hole_assignment_keeps_first(self):
        agent = _make_agent()
        bp = _bp_one_pocket_with_hole({"side": "oben", "alignment": "centered"})
        _mock_call_json(agent, {
            "assignments": [
                {"hole_feature_id": "bohrung_oben_1", "pocket_id": "tasche_oben_0"},
                {"hole_feature_id": "bohrung_oben_1", "pocket_id": "tasche_oben_0"},
            ]
        })
        result = agent.extract("in der tasche bohrung", bp)
        assert len(result["features_to_add"]) == 1


class TestLLMInputContents:
    """Sicherstellen dass das LLM die Listings als Mapping-Input bekommt
    (nicht erneut den ganzen User-Text mit Position-Infos parst)."""

    def test_holes_listing_includes_source_text(self):
        agent = _make_agent()
        bp = _bp_one_pocket_with_hole({"side": "oben", "alignment": "centered"})
        captured = {}

        def fake(prompt, system=None):
            captured["prompt"] = prompt
            return {"assignments": []}

        agent.call_json = MagicMock(side_effect=fake)
        agent.extract("in der tasche eine bohrung", bp)
        assert "bohrung_oben_1" in captured["prompt"]
        assert "tasche_oben_0" in captured["prompt"]
        # source_text sollte aus den notes des Upstream-Features kommen
        assert "15mm nach rechts" in captured["prompt"]


class TestRun965da548Regression:
    """Integration: pocket_child_placer + blueprint_resolver auf der echten
    Spec aus Run 965da548. Vor dem Refactor war hole_in_tasche_oben_0_1 mit
    offset (74.7721, 72.6047) platziert — nur 15mm rechts rotiert, "10mm
    nach oben" verloren. Nach dem Refactor muss (73.04, 82.45) rauskommen
    (Pocket-Mitte 60,70 + rotated 13.04, 12.45)."""

    def test_full_pipeline_preserves_both_offsets(self):
        from src.tools.blueprint_resolver import resolve_blueprint

        # Simuliere den Output des feature_definierer: ein Wuerfel + Tasche
        # + drei Bohrungen, die alle obenauf platziert wurden (parent=wuerfel)
        # und ihre korrekten Position-Werte tragen.
        upstream_bp = {
            "build_order": ["wuerfel", "tasche_oben_0", "bohrung_oben_1",
                            "bohrung_oben_2"],
            "features": {
                "wuerfel": {"id": "wuerfel", "type": "box",
                             "params": {"x": 200, "y": 200, "z": 200},
                             "parent": None, "operation": "add",
                             "orientation": "standard"},
                "tasche_oben_0": {
                    "id": "tasche_oben_0", "type": "pocket_rect",
                    "params": {"x": 60, "y": 40, "depth": 10},
                    "parent": "wuerfel", "operation": "subtract",
                    "orientation": "standard",
                    "position": {"side": "oben", "alignment": "centered",
                                  "edge_distances": {"top": 30, "right": 40},
                                  "angle_deg": 10.0, "notes": "von_kanten"},
                },
                "bohrung_oben_1": {
                    "id": "bohrung_oben_1", "type": "hole_single",
                    "params": {"diameter": 10, "depth": 10},
                    "parent": "wuerfel", "operation": "subtract",
                    "orientation": "standard",
                    "position": {"side": "oben", "alignment": "centered",
                                  "edge_distances": None, "angle_deg": 0.0,
                                  "notes": "von_mitte",
                                  "center_offset": {"top": 10, "right": 15}},
                    "notes": "in der tasche um 15mm nach rechts und 10mm nach oben",
                },
                "bohrung_oben_2": {
                    "id": "bohrung_oben_2", "type": "hole_single",
                    "params": {"diameter": 10, "depth": 10},
                    "parent": "wuerfel", "operation": "subtract",
                    "orientation": "standard",
                    "position": {"side": "oben", "alignment": "centered",
                                  "edge_distances": {"top": 10, "left": 10},
                                  "angle_deg": 0.0, "notes": "von_kanten"},
                    "notes": "in der tasche von linker kante 10 von oberer 10",
                },
            },
        }

        # pocket_child_placer mit gemocktem LLM: ordnet beide Bohrungen
        # der Tasche zu.
        agent = _make_agent()
        _mock_call_json(agent, {
            "assignments": [
                {"hole_feature_id": "bohrung_oben_1", "pocket_id": "tasche_oben_0"},
                {"hole_feature_id": "bohrung_oben_2", "pocket_id": "tasche_oben_0"},
            ]
        })
        spec = ("200mm wuerfel oben tasche 60x40x10 um 10 grad gedreht "
                "in der tasche 15 nach rechts 10 nach oben bohrung 10mm tief 10 "
                "in der tasche von linker kante 10 von oberer 10 bohrung 10mm tief 10")
        result = agent.extract(spec, upstream_bp)

        # Merge wie es planning_nodes.py auch tut.
        merged = dict(upstream_bp["features"])
        for rid in result["feature_ids_to_remove"]:
            merged.pop(rid, None)
        for fid, feat in result["features_to_add"].items():
            merged[fid] = feat
        new_order = [fid for fid in upstream_bp["build_order"]
                     if fid not in result["feature_ids_to_remove"]]
        for fid in result["features_to_add"]:
            new_order.append(fid)
        post_pcp_bp = {"description": "test", "build_order": new_order,
                       "features": merged}

        # Resolver laufen lassen.
        resolved = resolve_blueprint(post_pcp_bp)
        feats = resolved["features"]

        # Hole 1: Pocket-Mitte (60, 70), angle 10°, lokal (15, 10)
        # → erwartetes Welt-offset:
        #     ox = 60 + 15·cos10° - 10·sin10° = 60 + 14.7721 - 1.7365 = 73.036
        #     oy = 70 + 15·sin10° + 10·cos10° = 70 + 2.6047 + 9.8481 = 82.453
        h1 = feats["hole_in_tasche_oben_0_1"]["placement"]
        assert abs(h1["offset_x"] - 73.0356) < 0.01, \
            f"Hole 1 offset_x falsch: {h1['offset_x']}, erwartet ~73.04"
        assert abs(h1["offset_y"] - 82.4528) < 0.01, \
            f"Hole 1 offset_y falsch: {h1['offset_y']}, erwartet ~82.45"

        # Hole 2: edge_distances {top: 10, left: 10} im Pocket-Lokalframe
        # Pocket 60x40 → Mitte (0,0), top-left = (-30, +20)
        # 10 von links / 10 von oben → lokal (-20, 10)
        # rotated 10°: (-20·cos10° - 10·sin10°, -20·sin10° + 10·cos10°)
        #            = (-19.696 - 1.7365, -3.4730 + 9.8481)
        #            = (-21.4326, 6.3751)
        # + Pocket (60, 70) = (38.5674, 76.3751)
        h2 = feats["hole_in_tasche_oben_0_2"]["placement"]
        assert abs(h2["offset_x"] - 38.5674) < 0.01, \
            f"Hole 2 offset_x falsch: {h2['offset_x']}"
        assert abs(h2["offset_y"] - 76.3751) < 0.01, \
            f"Hole 2 offset_y falsch: {h2['offset_y']}"
