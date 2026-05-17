"""Tests for NormalizerAgent.define_feature() — W4 deterministic path.

ADR 0014 §3 / W4: define_feature() no longer calls an LLM Normalizer.
The classifier output (`typ`, `seite`, `parameter_hints`) is fed straight
into _build_normalized_from_hints → build_feature. One Textverstaendnis-
Schritt per action; rest deterministic. Pre-W4 tests that mocked
NormalizerAgent.normalize() are obsolete (the method is no longer in the
call path); the surviving tests below drive everything via parameter_hints.
"""


def _make_agent():
    from src.agents.normalizer_agent import NormalizerAgent
    return NormalizerAgent()


def _klass(**overrides):
    base = {
        "typ": "bohrung",
        "seite": "rechts",
        "beschreibung": "rechts eine Bohrung 8mm 10 tief",
        "teil_id": "wuerfel",
        "phrase_idx": 0,
        "parent_phrase_idx": None,
        "parameter_hints": {"durchmesser": 8, "tiefe": 10},
    }
    base.update(overrides)
    return base


def _teil(**overrides):
    base = {
        "id": "wuerfel",
        "type": "box",
        "raw_params": {"x": 200, "y": 200, "z": 200},
    }
    base.update(overrides)
    return base


# ── Standard-Pfad ──────────────────────────────────────────────────────


def test_simple_bohrung_full_output_shape():
    agent = _make_agent()
    feat = agent.define_feature(_klass(), _teil())

    assert feat["type"] == "hole_single"
    assert feat["id"] == "bohrung_rechts_0"
    assert feat["params"]["diameter"] == 8
    assert feat["params"]["depth"] == 10
    assert feat["position"]["side"] == "rechts"
    assert feat["operation"] == "subtract"
    assert feat["parent"] == "wuerfel"
    assert feat["_phrase_idx"] == 0
    assert feat["_parent_phrase_idx"] is None


def test_markers_propagate_for_nested_child():
    agent = _make_agent()
    feat = agent.define_feature(
        _klass(phrase_idx=2, parent_phrase_idx=1),
        _teil(),
    )
    assert feat["_phrase_idx"] == 2
    assert feat["_parent_phrase_idx"] == 1


def test_parent_defaults_to_teil_id():
    agent = _make_agent()
    feat = agent.define_feature(_klass(), _teil(id="my_part"))
    assert feat["parent"] == "my_part"


# ── Sentinel-Typen → None ──────────────────────────────────────────────


def test_returns_none_for_classifier_unbekannt():
    """W4: with the LLM Normalizer gone, an `unbekannt`/empty classifier
    typ has no fallback source — define_feature returns None and the
    caller drops the action. Replaces the pre-W4 cross-family-rescue."""
    agent = _make_agent()
    assert agent.define_feature(_klass(typ="unbekannt"), _teil()) is None
    assert agent.define_feature(_klass(typ=""), _teil()) is None


# ── parameter_hints → params ───────────────────────────────────────────


def test_hints_drive_params():
    agent = _make_agent()
    feat = agent.define_feature(
        _klass(parameter_hints={"durchmesser": 8, "tiefe": 10}),
        _teil(),
    )
    assert feat["params"]["diameter"] == 8
    assert feat["params"]["depth"] == 10


def test_hint_overrides_default_diameter():
    """hints provide the only param source — no second parser to merge."""
    agent = _make_agent()
    feat = agent.define_feature(
        _klass(parameter_hints={"durchmesser": 8}),
        _teil(),
    )
    assert feat["params"]["diameter"] == 8


def test_edge_distances_from_hints():
    """W4 regression: classifier emits abstand_oben/_links → both reach the
    feature's edge_distances. Pre-W4 a normalizer-zero-drop could swap one
    of them to 0; now there is no second source to drift."""
    agent = _make_agent()
    feat = agent.define_feature(
        _klass(typ="tasche",
               beschreibung="oben eine Tasche 20x30x10 oben 10mm links 10mm",
               seite="oben",
               parameter_hints={"laenge": 20, "breite": 30, "tiefe": 10,
                                "abstand_oben": 10, "abstand_links": 10}),
        _teil(),
    )
    assert feat["position"]["edge_distances"]["left"] == 10
    assert feat["position"]["edge_distances"]["top"] == 10


# ── Slot richtung / laenge / angle_deg ────────────────────────────────


def test_slot_direction_hint_promoted_before_length_inference():
    """The richtung hint must reach build_feature so slot-length defaulting
    picks the correct parent axis. "entlang y" on the top face → length=y_dim."""
    agent = _make_agent()
    feat = agent.define_feature(
        _klass(typ="nut",
               seite="oben",
               beschreibung="oben eine nut 5x5 entlang y-achse",
               parameter_hints={"breite": 5, "tiefe": 5, "richtung": "y"}),
        _teil(raw_params={"x": 100, "y": 60, "z": 20}),
    )
    assert feat["params"]["length"] == 60
    assert feat["position"]["angle_deg"] == 90.0


def test_slot_y_axis_sets_angle_deg_90():
    agent = _make_agent()
    feat = agent.define_feature(
        _klass(typ="nut",
               beschreibung="oben eine nut 5x5 entlang y-achse laenge 40mm",
               seite="oben",
               parameter_hints={"breite": 5, "tiefe": 5, "laenge": 40,
                                "richtung": "y"}),
        _teil(),
    )
    assert feat["type"] == "slot"
    assert feat["position"]["angle_deg"] == 90.0


def test_slot_y_axis_combines_with_explicit_rotation():
    """Slot 'entlang y-achse 15 grad gedreht' → 90 + 15 = 105."""
    agent = _make_agent()
    feat = agent.define_feature(
        _klass(typ="nut",
               beschreibung="oben eine nut 5x5 entlang y-achse 15 grad gedreht",
               seite="oben",
               parameter_hints={"breite": 5, "tiefe": 5, "laenge": 40,
                                "richtung": "y", "rotation_deg": 15}),
        _teil(),
    )
    assert feat["position"]["angle_deg"] == 105.0


def test_slot_x_axis_keeps_angle_deg_0():
    agent = _make_agent()
    feat = agent.define_feature(
        _klass(typ="nut", seite="oben",
               parameter_hints={"breite": 5, "tiefe": 5, "laenge": 40,
                                "richtung": "x"}),
        _teil(),
    )
    assert feat["position"]["angle_deg"] == 0.0


def test_slot_without_length_defaults_to_parent_axis_dimension():
    """Slot ohne explizite Laenge → durchgehend entlang Achse aus Teil-Dim."""
    agent = _make_agent()
    feat = agent.define_feature(
        _klass(typ="nut",
               beschreibung="oben eine nut 5x5 entlang x-achse 10mm nach rechts versetzt",
               seite="oben",
               parameter_hints={"breite": 5, "tiefe": 5,
                                "richtung": "x", "versatz_rechts": 10}),
        _teil(raw_params={"x": 100, "y": 80, "z": 30}),
    )
    assert feat["params"]["length"] == 100
    assert feat["position"]["center_offset"] == {"right": 10}


def test_slot_explicit_length_is_kept():
    agent = _make_agent()
    feat = agent.define_feature(
        _klass(typ="nut", seite="oben",
               parameter_hints={"breite": 5, "tiefe": 5, "laenge": 40,
                                "richtung": "x"}),
        _teil(raw_params={"x": 100, "y": 80, "z": 30}),
    )
    assert feat["params"]["length"] == 40


def test_slot_right_face_y_axis_keeps_angle_deg_0():
    """Auf >X Face ist die lokale horizontale Achse global Y."""
    agent = _make_agent()
    feat = agent.define_feature(
        _klass(typ="nut", seite="rechts",
               parameter_hints={"breite": 5, "tiefe": 5, "laenge": 40,
                                "richtung": "y"}),
        _teil(),
    )
    assert feat["position"]["angle_deg"] == 0.0


def test_slot_right_face_z_axis_sets_angle_deg_90():
    """Auf >X Face ist die lokale vertikale Achse global Z."""
    agent = _make_agent()
    feat = agent.define_feature(
        _klass(typ="nut", seite="rechts",
               parameter_hints={"breite": 5, "tiefe": 5, "laenge": 40,
                                "richtung": "z"}),
        _teil(),
    )
    assert feat["position"]["angle_deg"] == 90.0


def test_slot_endpoints_resolve_to_axis_without_explicit_richtung():
    """W4: anfang_links/ende_links allein müssen für richtung=x reichen,
    auch wenn der Klassifizierer kein 'richtung' im Hint emittiert hat."""
    agent = _make_agent()
    feat = agent.define_feature(
        _klass(typ="nut", seite="oben",
               beschreibung="oben eine nut 5x3 anfangspunkt 20mm von linker kante "
                            "endpunkt 80mm von linker kante",
               parameter_hints={"breite": 5, "tiefe": 3,
                                "anfang_links": 20, "ende_links": 80}),
        _teil(raw_params={"x": 100, "y": 80, "z": 30}),
    )
    assert feat["type"] == "slot"
    assert feat["params"]["length"] == 60
    assert feat["position"]["angle_deg"] == 0.0  # x-Achse → 0


# ── Linear pattern (W3 + W4) ───────────────────────────────────────────


def test_hole_pattern_linear_direction_hint_becomes_param():
    """W3: linear_classifier emits typ=bohrungsreihe directly. W4: richtung
    flows through from the classifier hint."""
    agent = _make_agent()
    feat = agent.define_feature(
        _klass(typ="bohrungsreihe",
               seite="vorne",
               beschreibung="vorne eine bohrungsreihe entlang z mit 4 bohrungen",
               parameter_hints={"anzahl": 4, "durchmesser": 5, "tiefe": 4,
                                "abstand": 12, "richtung": "z"}),
        _teil(raw_params={"x": 120, "y": 90, "z": 50}),
    )
    assert feat["type"] == "hole_pattern_linear"
    assert feat["params"]["direction"] == "z"
    assert feat["position"]["notes"] == "entlang Z"


# ── Anchor regex (W5 cleanup target — bleibt fuer W4) ──────────────────


def test_slot_right_edge_anchor_from_phrase():
    agent = _make_agent()
    feat = agent.define_feature(
        _klass(typ="nut",
               beschreibung="oben eine nut 5x5 entlang y-achse laenge 40mm "
                            "liegt auf rechter kante an, 10mm nach oben versetzt",
               seite="oben",
               parameter_hints={"breite": 5, "tiefe": 5, "laenge": 40,
                                "richtung": "y",
                                "kante_rechts": 0, "versatz_oben": 10}),
        _teil(),
    )
    assert feat["position"]["anchor"] == {
        "child_point": "center",
        "parent_point": "right_edge",
        "offset": {"top": 10},
    }
    assert "center_offset" not in feat["position"]
    assert "edge_distances" not in feat["position"]


def test_bare_corner_phrase_is_positioning_not_anchor():
    """Regressions-Wache: eine blosse Ecken-Erwaehnung ohne expliziten
    Parent-Verweis ist Positionierung, KEIN Anker."""
    agent = _make_agent()
    feat = agent.define_feature(
        _klass(typ="nut",
               beschreibung="oben eine nut 5x5 entlang y-achse laenge 30mm "
                            "obere rechte ecke 10mm nach unten und 20mm nach links versetzt",
               seite="oben",
               parameter_hints={"breite": 5, "tiefe": 5, "laenge": 30,
                                "richtung": "y",
                                "versatz_unten": 10, "versatz_links": 20}),
        _teil(),
    )
    assert "anchor" not in feat["position"], (
        f"bare corner darf keinen Anker erzeugen: {feat['position']}"
    )
    assert feat["position"].get("center_offset") == {"bottom": 10, "left": 20}


def test_pocket_corner_to_corner_anchor_uses_child_corner():
    agent = _make_agent()
    feat = agent.define_feature(
        _klass(typ="tasche",
               beschreibung="oben eine tasche 30x20x10 obere rechte ecke "
                            "der tasche auf obere rechte ecke des wuerfels",
               seite="oben",
               parameter_hints={"laenge": 30, "breite": 20, "tiefe": 10}),
        _teil(),
    )
    assert feat["position"]["anchor"] == {
        "child_point": "top_right",
        "parent_point": "top_right",
    }


def test_hole_edge_to_edge_anchor_uses_child_edge():
    agent = _make_agent()
    feat = agent.define_feature(
        _klass(typ="bohrung",
               beschreibung="oben eine 5mm bohrung 5 tief rechte kante "
                            "der bohrung auf rechte kante der platte",
               seite="oben",
               parameter_hints={"durchmesser": 5, "tiefe": 5,
                                "kante_rechts": 0}),
        _teil(),
    )
    assert feat["position"]["anchor"] == {
        "child_point": "right_edge",
        "parent_point": "right_edge",
    }


# ── Hint-Key-Rename ────────────────────────────────────────────────────


def test_rotation_deg_hint_maps_to_drehung_then_angle_deg():
    """rotation_deg hint → params['drehung'] → feature.position.angle_deg."""
    agent = _make_agent()
    feat = agent.define_feature(
        _klass(typ="tasche",
               beschreibung="oben eine Tasche 60x40x10 um 10 grad gedreht",
               seite="oben",
               parameter_hints={"laenge": 60, "breite": 40, "tiefe": 10,
                                "rotation_deg": 10}),
        _teil(),
    )
    assert feat["type"] == "pocket_rect"
    assert feat["position"]["angle_deg"] == 10.0


def test_pocket_hoehe_hint_maps_to_tiefe():
    """Pocket-Wording 'Hoehe' = Schnitttiefe → build_feature liest tiefe."""
    agent = _make_agent()
    feat = agent.define_feature(
        _klass(typ="tasche", seite="oben",
               parameter_hints={"laenge": 60, "breite": 40, "hoehe": 8}),
        _teil(),
    )
    assert feat["params"]["depth"] == 8


def test_hints_with_none_values_are_skipped():
    agent = _make_agent()
    feat = agent.define_feature(
        _klass(parameter_hints={"durchmesser": None, "tiefe": 10}),
        _teil(),
    )
    # None hint is skipped — durchmesser falls back to build_feature default
    assert feat["params"]["depth"] == 10


# ── seite ──────────────────────────────────────────────────────────────


def test_classifier_seite_propagates_verbatim():
    """seite from the classifier is the source of truth — no second-guessing."""
    agent = _make_agent()
    feat = agent.define_feature(_klass(seite="rechts"), _teil())
    assert feat["position"]["side"] == "rechts"


# ── Module-level helpers ───────────────────────────────────────────────


def test_build_normalized_from_hints_position_corner():
    """Two perpendicular abstand_* keys → corner position token."""
    from src.agents.normalizer_agent import _build_normalized_from_hints
    n = _build_normalized_from_hints({
        "typ": "tasche", "seite": "oben",
        "parameter_hints": {"abstand_oben": 10, "abstand_rechts": 15,
                            "laenge": 20, "breite": 30, "tiefe": 5},
    })
    assert n["position"] == "oben-rechts"


def test_build_normalized_from_hints_position_zentriert():
    from src.agents.normalizer_agent import _build_normalized_from_hints
    n = _build_normalized_from_hints({
        "typ": "tasche", "seite": "oben",
        "parameter_hints": {"laenge": 20, "breite": 30, "tiefe": 5},
    })
    assert n["position"] == "zentriert"


def test_build_normalized_from_hints_endpoint_richtung():
    from src.agents.normalizer_agent import _build_normalized_from_hints
    n = _build_normalized_from_hints({
        "typ": "nut", "seite": "oben",
        "parameter_hints": {"breite": 5, "tiefe": 3,
                            "anfang_links": 20, "ende_links": 80},
    })
    assert n["richtung"] == "x"
