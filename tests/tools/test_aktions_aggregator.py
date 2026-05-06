"""Tests for src/tools/aktions_aggregator.py — Stage 4 of ADR 0003.

Kernverhalten:
  - Features werden nach _teil_id gruppiert, in spec-Reihenfolge sortiert.
  - parent wird fuer nested children auf die Parent-Feature-ID umgeschrieben.
  - Interne Marker (_teil_id, _phrase_idx, _parent_phrase_idx) verschwinden.
  - Teil-Orientation aus teil.beschreibung (hochkant/flach/standard).
"""
from __future__ import annotations

from src.tools.aktions_aggregator import aggregate


def _feat(**kwargs) -> dict:
    """Convenience: a SemanticFeature with sensible defaults."""
    base = {
        "id": "bohrung_rechts_0",
        "type": "hole_single",
        "params": {"diameter": 8, "depth": 10},
        "position": {"side": "rechts", "alignment": "centered",
                     "edge_distances": None, "angle_deg": 0.0, "notes": ""},
        "operation": "subtract",
        "parent": "wuerfel",
        "_teil_id": "wuerfel",
        "_phrase_idx": 0,
        "_parent_phrase_idx": None,
    }
    base.update(kwargs)
    return base


def _teil(id_: str = "wuerfel", **kwargs) -> dict:
    base = {
        "id": id_,
        "type": "box",
        "raw_params": {"x": 200, "y": 200, "z": 200},
    }
    base.update(kwargs)
    return base


# ── Empty / Edge ───────────────────────────────────────────────────────


def test_empty_features_yields_empty_features_per_teil():
    out = aggregate([], [_teil()])
    assert len(out) == 1
    assert out[0]["id"] == "wuerfel"
    assert out[0]["features"] == []


def test_empty_teile_yields_empty_list():
    assert aggregate([_feat()], []) == []


# ── Standard ───────────────────────────────────────────────────────────


def test_single_feature_passes_through_with_markers_stripped():
    feat = _feat()
    out = aggregate([feat], [_teil()])

    assert len(out) == 1
    assert len(out[0]["features"]) == 1
    f = out[0]["features"][0]
    assert "_teil_id" not in f
    assert "_phrase_idx" not in f
    assert "_parent_phrase_idx" not in f
    # Parent stays the teil_id for top-level features
    assert f["parent"] == "wuerfel"
    # Original feature dict is NOT mutated
    assert "_teil_id" in feat


def test_teil_definition_shape():
    out = aggregate([_feat()], [_teil(beschreibung="200mm wuerfel")])
    td = out[0]
    assert td["id"] == "wuerfel"
    assert td["type"] == "box"
    assert td["params"] == {"x": 200, "y": 200, "z": 200}
    assert td["orientation"] == "standard"
    assert isinstance(td["features"], list)


# ── parent-Resolution ──────────────────────────────────────────────────


def test_nested_child_parent_rewritten_to_pocket_id():
    pocket = _feat(
        id="tasche_oben_0", type="pocket_rect",
        params={"x": 60, "y": 40, "depth": 10},
        operation="subtract",
        position={"side": "oben"},
        _phrase_idx=0, _parent_phrase_idx=None,
    )
    bohrung = _feat(
        id="bohrung_oben_1", type="hole_single",
        params={"diameter": 8, "depth": 10},
        position={"side": "oben"},
        _phrase_idx=1, _parent_phrase_idx=0,
    )
    out = aggregate([pocket, bohrung], [_teil()])

    feats = out[0]["features"]
    assert feats[0]["id"] == "tasche_oben_0"
    assert feats[0]["parent"] == "wuerfel"
    assert feats[1]["id"] == "bohrung_oben_1"
    assert feats[1]["parent"] == "tasche_oben_0"


def test_two_children_share_one_pocket_parent():
    pocket = _feat(id="tasche_0", type="pocket_rect",
                    _phrase_idx=0, _parent_phrase_idx=None)
    hole_a = _feat(id="bohrung_a", _phrase_idx=1, _parent_phrase_idx=0)
    hole_b = _feat(id="bohrung_b", _phrase_idx=2, _parent_phrase_idx=0)

    out = aggregate([pocket, hole_a, hole_b], [_teil()])
    feats = {f["id"]: f for f in out[0]["features"]}
    assert feats["bohrung_a"]["parent"] == "tasche_0"
    assert feats["bohrung_b"]["parent"] == "tasche_0"


def test_dangling_parent_phrase_idx_falls_back_to_teil_id():
    """Wenn _parent_phrase_idx auf eine nicht vorhandene Phrase zeigt
    (Splitter-Glitch), bleibt parent=teil_id und der Aggregator loggt."""
    orphan = _feat(_phrase_idx=1, _parent_phrase_idx=99)
    out = aggregate([orphan], [_teil()])
    assert out[0]["features"][0]["parent"] == "wuerfel"


# ── Reihenfolge & Multi-Teil ───────────────────────────────────────────


def test_features_sorted_by_phrase_idx_within_teil():
    f0 = _feat(id="f0", _phrase_idx=0)
    f1 = _feat(id="f1", _phrase_idx=1)
    f2 = _feat(id="f2", _phrase_idx=2)
    # Out of order on input
    out = aggregate([f2, f0, f1], [_teil()])
    ids = [f["id"] for f in out[0]["features"]]
    assert ids == ["f0", "f1", "f2"]


def test_features_split_per_teil_no_cross_contamination():
    a = _feat(id="a_feat", _teil_id="wuerfel", parent="wuerfel")
    b = _feat(id="b_feat", _teil_id="platte", parent="platte")
    out = aggregate(
        [a, b],
        [_teil("wuerfel"), _teil("platte", raw_params={"x": 100, "y": 80, "z": 20})],
    )
    by_id = {td["id"]: td for td in out}
    assert [f["id"] for f in by_id["wuerfel"]["features"]] == ["a_feat"]
    assert [f["id"] for f in by_id["platte"]["features"]] == ["b_feat"]


def test_per_teil_phrase_idx_independent():
    """phrase_idx zaehlt pro Teil — _parent_phrase_idx muss innerhalb
    des Teils aufloesen, nicht teil-uebergreifend."""
    pocket_a = _feat(id="tasche_a", _teil_id="wuerfel",
                      _phrase_idx=0, _parent_phrase_idx=None)
    bohrung_a = _feat(id="bohrung_a", _teil_id="wuerfel",
                       _phrase_idx=1, _parent_phrase_idx=0)
    pocket_b = _feat(id="tasche_b", _teil_id="platte",
                      _phrase_idx=0, _parent_phrase_idx=None)
    bohrung_b = _feat(id="bohrung_b", _teil_id="platte",
                       _phrase_idx=1, _parent_phrase_idx=0)

    out = aggregate(
        [pocket_a, bohrung_a, pocket_b, bohrung_b],
        [_teil("wuerfel"), _teil("platte")],
    )
    by_id = {td["id"]: td for td in out}
    bohrung_a_out = next(f for f in by_id["wuerfel"]["features"]
                          if f["id"] == "bohrung_a")
    bohrung_b_out = next(f for f in by_id["platte"]["features"]
                          if f["id"] == "bohrung_b")
    assert bohrung_a_out["parent"] == "tasche_a"
    assert bohrung_b_out["parent"] == "tasche_b"


# ── Orientation ────────────────────────────────────────────────────────


def test_orientation_hochkant_keywords():
    for kw in ("hochkant", "stehend", "aufrecht"):
        out = aggregate([], [_teil(beschreibung=f"platte 100x80x20 {kw}")])
        assert out[0]["orientation"] == "hochkant"


def test_orientation_flach_keywords():
    for kw in ("flach", "liegend"):
        out = aggregate([], [_teil(beschreibung=f"platte 100x80x20 {kw}")])
        assert out[0]["orientation"] == "flach"


def test_orientation_default_standard():
    out = aggregate([], [_teil(beschreibung="200mm wuerfel")])
    assert out[0]["orientation"] == "standard"


def test_orientation_missing_beschreibung_is_standard():
    out = aggregate([], [_teil()])
    assert out[0]["orientation"] == "standard"


# ── Teil-Filter ────────────────────────────────────────────────────────


def test_features_for_unknown_teil_are_dropped():
    """Wenn ein Feature ein _teil_id traegt das nicht in `teile` ist,
    landet es in keiner teil_definition. Caller-Bug, aber graceful."""
    rogue = _feat(_teil_id="ghost_teil")
    out = aggregate([rogue], [_teil("wuerfel")])
    assert len(out) == 1
    assert out[0]["features"] == []


def test_feature_without_teil_id_marker_uses_parent_fallback():
    """Aelterer Feature ohne _teil_id Marker → falle auf parent-Field zurueck."""
    feat = _feat()
    feat.pop("_teil_id")
    feat["parent"] = "wuerfel"
    out = aggregate([feat], [_teil()])
    assert len(out[0]["features"]) == 1
