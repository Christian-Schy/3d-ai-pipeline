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


def test_hints_do_not_override_normalizer_parses():
    """Normalizer extracted durchmesser=10 explicitly; hint says 8 → keep 10."""
    agent = _make_agent()
    agent.normalize = MagicMock(return_value=_norm(
        parameter={"durchmesser": 10, "tiefe": 10},
    ))
    feat = agent.define_feature(
        _klass(parameter_hints={"durchmesser": 8}),
        _teil(),
    )
    assert feat["params"]["diameter"] == 10


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
