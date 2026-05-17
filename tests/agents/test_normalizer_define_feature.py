"""Tests for NormalizerAgent.define_feature() — Stufe 3 ADR 0003.

Kernverhalten:
  - Eingabe: klassifizierte Aktion (Stufe 2 Output) + Teil
  - Ausgabe: SemanticFeature mit _phrase_idx / _parent_phrase_idx Markern
  - Reconciliation: Classifier-typ und Normalizer-typ. Selbe Familie →
    Normalizer (spezifischer); andere Familie / "ignorieren" → Classifier.
  - parameter_hints fuellen Luecken in normalizer.parameter, ueberschreiben
    aber NICHT was der Normalizer aus dem Text geparst hat.
  - rotation_deg-Hint wird auf "drehung" gemappt und landet als angle_deg
    in feature.position.
"""

from unittest.mock import MagicMock


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


def _norm(**overrides):
    """Return value the mocked normalize() emits (NormalizerAgent's dict)."""
    base = {
        "typ": "bohrung",
        "seite": "rechts",
        "position": "zentriert",
        "richtung": "",
        "parameter": {"durchmesser": 8, "tiefe": 10},
        "notes": "",
    }
    base.update(overrides)
    return base


# ── Standard-Pfad ──────────────────────────────────────────────────────


def test_simple_bohrung_full_output_shape():
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm())

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
    agent.normalize = MagicMock(return_value=_norm())

    feat = agent.define_feature(
        _klass(phrase_idx=2, parent_phrase_idx=1),
        _teil(),
    )

    assert feat["_phrase_idx"] == 2
    assert feat["_parent_phrase_idx"] == 1


def test_parent_defaults_to_teil_id():
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm())
    feat = agent.define_feature(_klass(), _teil(id="my_part"))
    assert feat["parent"] == "my_part"


# ── Type-Reconciliation ────────────────────────────────────────────────


def test_normalizer_specific_typ_kept_when_family_matches():
    """classifier='bohrung', normalizer='eckbohrungen' (same family)
    → keep normalizer's eckbohrungen → feature_type=hole_pattern_grid."""
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm(
        typ="eckbohrungen",
        position="von_kanten",
        parameter={"anzahl": 4, "abstand_kante": 20,
                   "bohr_durchmesser": 10, "tiefe": "durch"},
    ))

    feat = agent.define_feature(
        _klass(typ="bohrung",
               beschreibung="4 Eckbohrungen je 20mm von den Kanten 10mm Durchmesser durch",
               parameter_hints={}),
        _teil(),
    )
    assert feat["type"] == "hole_pattern_grid"


def test_classifier_overrides_when_family_diverges():
    """classifier='bohrung', normalizer='tasche' (different family)
    → trust classifier → feature_type=hole_single."""
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm(
        typ="tasche", parameter={"laenge": 60, "breite": 40, "tiefe": 10},
    ))
    feat = agent.define_feature(_klass(typ="bohrung"), _teil())
    assert feat["type"] == "hole_single"


def test_classifier_overrides_normalizer_ignorieren():
    """If normalizer says 'ignorieren' but classifier picked a real typ,
    we trust the classifier (Stufe 2 already gated placement vs feature)."""
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm(
        typ="ignorieren", parameter={},
    ))
    feat = agent.define_feature(_klass(typ="bohrung"), _teil())
    assert feat["type"] == "hole_single"


def test_unbekannt_classifier_keeps_normalizer_typ():
    """classifier='unbekannt' → normalizer's typ stays."""
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm(typ="nut",
                                                    richtung="x",
                                                    parameter={"breite": 5, "tiefe": 5}))
    feat = agent.define_feature(_klass(typ="unbekannt"), _teil())
    assert feat["type"] == "slot"


def test_returns_none_when_both_sentinel():
    """Run da35a6ce / e1def0fa regression: phrase 'vorne soll eine platte
    hin mit 140x20x40' is part declaration, not a feature. Classifier
    says 'unbekannt', normalizer says 'ignorieren' → MUST return None so
    no phantom hole_single ends up on the platte."""
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm(
        typ="ignorieren", parameter={},
    ))
    feat = agent.define_feature(_klass(typ="unbekannt"), _teil())
    assert feat is None


def test_returns_none_when_classifier_empty_and_normalizer_ignorieren():
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm(typ="ignorieren", parameter={}))
    feat = agent.define_feature(_klass(typ=""), _teil())
    assert feat is None


# ── parameter_hints Merge ──────────────────────────────────────────────


def test_hints_fill_missing_params():
    """Normalizer didn't extract durchmesser; classifier hint fills it."""
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm(parameter={}))

    feat = agent.define_feature(
        _klass(parameter_hints={"durchmesser": 8, "tiefe": 10}),
        _teil(),
    )
    assert feat["params"]["diameter"] == 8
    assert feat["params"]["depth"] == 10


def test_classifier_hints_override_normalizer_parses():
    """ADR 0003 Stufe 5c: Classifier-Hints gewinnen ueber Normalizer-Parses.

    Hintergrund: der Normalizer laeuft mit think=false und droppt bei
    rotierten Taschen mit edge_distances gelegentlich einen Wert auf 0
    (Bug 4 in Run 3db7d152). Wenn der Klassifizierer einen Hint
    explizit emittiert, ueberschreibt er den Normalizer-Parse.
    """
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm(
        parameter={"durchmesser": 10, "tiefe": 10},
    ))
    feat = agent.define_feature(
        _klass(parameter_hints={"durchmesser": 8}),
        _teil(),
    )
    assert feat["params"]["diameter"] == 8


def test_classifier_hint_overrides_normalizer_zero_value():
    """Bug-4-Fall: Normalizer hat abstand_links=0 (verloren), Klassifizierer
    hat abstand_links=10 (korrekt extrahiert) → Hint gewinnt."""
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm(
        typ="tasche",
        position="von_kanten",
        parameter={"laenge": 20, "breite": 30, "tiefe": 10,
                   "abstand_oben": 10, "abstand_links": 0},
    ))
    feat = agent.define_feature(
        _klass(typ="tasche",
               beschreibung="oben eine Tasche 20x30x10 die obere Kante "
                            "von oben 10mm die linke Seite von links 10mm",
               seite="oben",
               parameter_hints={"laenge": 20, "breite": 30, "tiefe": 10,
                                "abstand_oben": 10, "abstand_links": 10}),
        _teil(),
    )
    assert feat["position"]["edge_distances"]["left"] == 10
    assert feat["position"]["edge_distances"]["top"] == 10


def test_classifier_direction_hint_promoted_before_slot_length_inference():
    """`richtung` is the one non-numeric classifier hint.

    It must become the normalizer's top-level direction before slot length
    inference runs; otherwise "entlang y" on the top face would infer x-length.
    """
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm(
        typ="nut",
        seite="oben",
        richtung="",
        parameter={"breite": 5, "tiefe": 5},
    ))
    feat = agent.define_feature(
        _klass(typ="nut",
               seite="oben",
               beschreibung="oben eine nut 5x5 entlang y-achse",
               parameter_hints={"breite": 5, "tiefe": 5, "richtung": "y"}),
        _teil(raw_params={"x": 100, "y": 60, "z": 20}),
    )
    assert feat["params"]["length"] == 60
    assert feat["position"]["angle_deg"] == 90.0


def test_hole_pattern_linear_direction_hint_becomes_param():
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm(
        typ="bohrungsreihe",
        seite="vorne",
        richtung="",
        parameter={"anzahl": 4, "durchmesser": 5, "tiefe": 4, "abstand": 12},
    ))
    feat = agent.define_feature(
        _klass(typ="bohrung",
               seite="vorne",
               beschreibung="vorne eine bohrungsreihe entlang z mit 4 bohrungen",
               parameter_hints={"anzahl": 4, "durchmesser": 5, "tiefe": 4,
                                "abstand": 12, "richtung": "z"}),
        _teil(raw_params={"x": 120, "y": 90, "z": 50}),
    )
    assert feat["type"] == "hole_pattern_linear"
    assert feat["params"]["direction"] == "z"
    assert feat["position"]["notes"] == "entlang Z"


def test_hole_pattern_linear_direction_inferred_from_phrase():
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm(
        typ="bohrungsreihe",
        seite="vorne",
        richtung="",
        parameter={"anzahl": 4, "durchmesser": 5, "tiefe": 4, "abstand": 12},
    ))
    feat = agent.define_feature(
        _klass(typ="bohrung",
               seite="vorne",
               beschreibung="vorne eine bohrungsreihe entlang z-achse mit 4 bohrungen",
               parameter_hints={"anzahl": 4, "durchmesser": 5, "tiefe": 4,
                                "abstand": 12}),
        _teil(raw_params={"x": 120, "y": 90, "z": 50}),
    )
    assert feat["type"] == "hole_pattern_linear"
    assert feat["params"]["direction"] == "z"
    assert feat["position"]["notes"] == "entlang Z"


def test_slot_y_axis_sets_angle_deg_90():
    """Slot 'entlang y-achse' → angle_deg=90 (deterministische Achsen→
    Winkel-Konvention aus N_kombo_basics notes.md). LLM erkennt richtung,
    Code mappt zu Winkel.
    """
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm(
        typ="nut",
        seite="oben",
        richtung="y",
        parameter={"breite": 5, "tiefe": 5, "laenge": 40},
    ))
    feat = agent.define_feature(
        _klass(typ="nut",
               beschreibung="oben eine nut 5x5 entlang y-achse laenge 40mm",
               seite="oben"),
        _teil(),
    )
    assert feat["type"] == "slot"
    assert feat["position"]["angle_deg"] == 90.0


def test_slot_y_axis_combines_with_explicit_rotation():
    """Slot 'entlang y-achse 15 grad gedreht' → 90 + 15 = 105."""
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm(
        typ="nut",
        seite="oben",
        richtung="y",
        parameter={"breite": 5, "tiefe": 5, "laenge": 40, "drehung": 15},
    ))
    feat = agent.define_feature(
        _klass(typ="nut",
               beschreibung="oben eine nut 5x5 entlang y-achse 15 grad gedreht",
               seite="oben"),
        _teil(),
    )
    assert feat["position"]["angle_deg"] == 105.0


def test_slot_x_axis_keeps_angle_deg_0():
    """Slot 'entlang x-achse' → angle_deg=0 (default; keine Achsen-Korrektur)."""
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm(
        typ="nut",
        seite="oben",
        richtung="x",
        parameter={"breite": 5, "tiefe": 5, "laenge": 40},
    ))
    feat = agent.define_feature(_klass(typ="nut", seite="oben"), _teil())
    assert feat["position"]["angle_deg"] == 0.0


def test_slot_without_length_defaults_to_parent_axis_dimension():
    """Slot ohne explizite Laenge bedeutet in N_kombo durchgehend entlang Achse."""
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm(
        typ="nut",
        seite="oben",
        richtung="x",
        parameter={"breite": 5, "tiefe": 5, "versatz_rechts": 10},
    ))
    feat = agent.define_feature(
        _klass(typ="nut",
               beschreibung="oben eine nut 5x5 entlang x-achse 10mm nach rechts versetzt",
               seite="oben",
               parameter_hints={"breite": 5, "tiefe": 5, "versatz_rechts": 10}),
        _teil(raw_params={"x": 100, "y": 80, "z": 30}),
    )
    assert feat["params"]["length"] == 100
    assert feat["position"]["center_offset"] == {"right": 10}


def test_slot_explicit_length_is_kept():
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm(
        typ="nut",
        seite="oben",
        richtung="x",
        parameter={"breite": 5, "tiefe": 5, "laenge": 40},
    ))
    feat = agent.define_feature(
        _klass(typ="nut", seite="oben",
               parameter_hints={"breite": 5, "tiefe": 5, "laenge": 40}),
        _teil(raw_params={"x": 100, "y": 80, "z": 30}),
    )
    assert feat["params"]["length"] == 40


def test_slot_right_face_y_axis_keeps_angle_deg_0():
    """Auf >X Face ist die lokale horizontale Achse global Y."""
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm(
        typ="nut",
        seite="rechts",
        richtung="y",
        parameter={"breite": 5, "tiefe": 5, "laenge": 40},
    ))
    feat = agent.define_feature(
        _klass(typ="nut", seite="rechts",
               parameter_hints={"breite": 5, "tiefe": 5, "laenge": 40}),
        _teil(),
    )
    assert feat["position"]["angle_deg"] == 0.0


def test_slot_right_face_z_axis_sets_angle_deg_90():
    """Auf >X Face ist die lokale vertikale Achse global Z."""
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm(
        typ="nut",
        seite="rechts",
        richtung="z",
        parameter={"breite": 5, "tiefe": 5, "laenge": 40},
    ))
    feat = agent.define_feature(
        _klass(typ="nut", seite="rechts",
               parameter_hints={"breite": 5, "tiefe": 5, "laenge": 40}),
        _teil(),
    )
    assert feat["position"]["angle_deg"] == 90.0


def test_slot_right_edge_anchor_from_phrase():
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm(
        typ="nut",
        seite="oben",
        position="von_kanten",
        richtung="y",
        parameter={"breite": 5, "tiefe": 5, "laenge": 40,
                   "kante_rechts": 0, "versatz_oben": 10},
    ))
    feat = agent.define_feature(
        _klass(typ="nut",
               beschreibung="oben eine nut 5x5 entlang y-achse laenge 40mm "
                            "liegt auf rechter kante an, 10mm nach oben versetzt",
               seite="oben",
               parameter_hints={"breite": 5, "tiefe": 5, "laenge": 40,
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
    Parent-Verweis ("liegt auf …" / "… der Tasche auf … des Wuerfels")
    ist Positionierung, KEIN Anker.

    Frueher fabrizierte `_infer_phrase_anchor` fuer jede Ecken-Erwaehnung
    einen Anker und ueberschrieb damit die Klassifizierer-Positionierung
    (Bug auf T_kombo t08). Jetzt: kein Anker — die Versatz-Werte bleiben
    als center_offset erhalten.
    """
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm(
        typ="nut",
        seite="oben",
        position="von_mitte",
        richtung="y",
        parameter={"breite": 5, "tiefe": 5, "laenge": 30},
    ))
    feat = agent.define_feature(
        _klass(typ="nut",
               beschreibung="oben eine nut 5x5 entlang y-achse laenge 30mm "
                            "obere rechte ecke 10mm nach unten und 20mm nach links versetzt",
               seite="oben",
               parameter_hints={"breite": 5, "tiefe": 5, "laenge": 30,
                                "versatz_unten": 10, "versatz_links": 20}),
        _teil(),
    )
    assert "anchor" not in feat["position"], (
        f"bare corner darf keinen Anker erzeugen: {feat['position']}"
    )
    assert feat["position"].get("center_offset") == {"bottom": 10, "left": 20}


def test_pocket_corner_to_corner_anchor_uses_child_corner():
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm(
        typ="tasche",
        seite="oben",
        parameter={"laenge": 30, "breite": 20, "tiefe": 10},
    ))
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
    agent.normalize = MagicMock(return_value=_norm(
        typ="bohrung",
        seite="oben",
        position="rechts",
        parameter={"durchmesser": 5, "tiefe": 5, "kante_rechts": 0},
    ))
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


def test_rotation_deg_hint_maps_to_drehung_then_angle_deg():
    """Classifier hints rotation_deg=10 → params['drehung']=10
    → feature.position.angle_deg=10."""
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm(
        typ="tasche",
        parameter={"laenge": 60, "breite": 40, "tiefe": 10},
    ))
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


def test_hints_with_none_values_are_skipped():
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm(parameter={}))
    feat = agent.define_feature(
        _klass(parameter_hints={"durchmesser": None, "tiefe": 10}),
        _teil(),
    )
    # None hint is skipped — durchmesser falls back to build_feature default
    assert feat["params"]["depth"] == 10


# ── Seite-Override ─────────────────────────────────────────────────────


def test_classifier_seite_overrides_normalizer_seite():
    """Stufe 2 already fixed seite (e.g. inherited from parent for nested).
    The normalizer must not silently flip it."""
    agent = _make_agent()
    # Normalizer parsed seite=oben from text; classifier insists rechts.
    agent.normalize = MagicMock(return_value=_norm(seite="oben"))
    feat = agent.define_feature(_klass(seite="rechts"), _teil())
    assert feat["position"]["side"] == "rechts"


# ── Module-level helpers ───────────────────────────────────────────────


def test_merge_param_hints_renames_rotation_deg():
    from src.agents.normalizer_agent import _merge_param_hints
    params: dict = {}
    _merge_param_hints(params, {"rotation_deg": 15})
    assert params == {"drehung": 15}


def test_merge_param_hints_maps_pocket_hoehe_to_tiefe():
    from src.agents.normalizer_agent import _merge_param_hints
    params: dict = {}
    _merge_param_hints(params, {"hoehe": 8})
    assert params == {"tiefe": 8}


def test_reconcile_typ_same_family_keeps_normalizer():
    from src.agents.normalizer_agent import _reconcile_typ
    assert _reconcile_typ("bohrung", "lochkreis") == "lochkreis"


def test_reconcile_typ_cross_family_returns_classifier():
    from src.agents.normalizer_agent import _reconcile_typ
    assert _reconcile_typ("bohrung", "tasche") == "bohrung"


def test_reconcile_typ_unknown_classifier_returns_normalizer():
    from src.agents.normalizer_agent import _reconcile_typ
    assert _reconcile_typ("unbekannt", "tasche") == "tasche"
    assert _reconcile_typ("", "bohrung") == "bohrung"


def test_reconcile_typ_normalizer_ignorieren_returns_classifier():
    from src.agents.normalizer_agent import _reconcile_typ
    assert _reconcile_typ("bohrung", "ignorieren") == "bohrung"
