"""tests/agents/test_aktions_klassifizierer.py — Unit tests for the
per-action classifier (Stufe 2 von ADR 0003).

Kernverhalten:
  - Splitter-Felder (teil_id, phrase_idx, parent_phrase_idx) werden 1:1
    durchgereicht — das LLM darf sie nicht ueberschreiben.
  - Phrase landet als beschreibung im Output.
  - typ wird auf 'unbekannt' gesetzt, wenn das LLM Mist liefert.
  - seite faellt auf 'oben' zurueck bei unbekanntem Wert.
  - parameter_hints muss ein Dict sein, sonst leeres Dict.
  - LLM-Exception → leere Klassifikation, Splitter-Felder bleiben.
"""

from unittest.mock import MagicMock


def _make_agent():
    from src.agents.aktions_klassifizierer import AktionsKlassifizierer
    return AktionsKlassifizierer()


def _phrase(phrase: str, **kwargs):
    """Splitter-konformes Phrase-Dict mit Default-Werten."""
    return {
        "phrase": phrase,
        "teil_id": kwargs.get("teil_id", "wuerfel"),
        "phrase_idx": kwargs.get("phrase_idx", 0),
        "parent_phrase_idx": kwargs.get("parent_phrase_idx"),
    }


def _teil(**kwargs):
    return {
        "id": kwargs.get("id", "wuerfel"),
        "type": kwargs.get("type", "box"),
        "raw_params": kwargs.get("raw_params", {"x": 100, "y": 100, "z": 100}),
    }


# ── Standard-Klassifikation ──────────────────────────────────────────────────


def test_simple_bohrung_classification():
    agent = _make_agent()
    agent.call_json = MagicMock(return_value={
        "typ": "bohrung",
        "seite": "rechts",
        "parameter_hints": {"durchmesser": 8, "tiefe": 10},
    })

    out = agent.classify(
        _phrase("rechts eine Bohrung 8mm 10 tief"),
        _teil(),
    )

    assert out["typ"] == "bohrung"
    assert out["seite"] == "rechts"
    assert out["parameter_hints"] == {"durchmesser": 8, "tiefe": 10}
    assert out["beschreibung"] == "rechts eine Bohrung 8mm 10 tief"


def test_tasche_with_rotation():
    agent = _make_agent()
    agent.call_json = MagicMock(return_value={
        "typ": "tasche",
        "seite": "oben",
        "parameter_hints": {"laenge": 60, "breite": 40, "tiefe": 10,
                            "rotation_deg": 10},
    })

    out = agent.classify(
        _phrase("oben eine Tasche 60x40x10 um 10 grad gedreht"),
        _teil(raw_params={"x": 200, "y": 200, "z": 200}),
    )

    assert out["typ"] == "tasche"
    assert out["parameter_hints"]["rotation_deg"] == 10


# ── Splitter-Felder werden durchgereicht ────────────────────────────────────


def test_splitter_fields_pass_through_unchanged():
    """teil_id, phrase_idx, parent_phrase_idx kommen aus dem Splitter
    und duerfen nicht durch das LLM ueberschrieben werden."""
    agent = _make_agent()
    # LLM versucht teil_id/phrase_idx zu setzen — das wird ignoriert.
    agent.call_json = MagicMock(return_value={
        "typ": "bohrung",
        "seite": "oben",
        "teil_id": "WRONG",
        "phrase_idx": 999,
        "parent_phrase_idx": 999,
        "parameter_hints": {},
    })

    out = agent.classify(
        _phrase(
            "in der Tasche eine Bohrung 5mm",
            teil_id="wuerfel",
            phrase_idx=3,
            parent_phrase_idx=2,
        ),
        _teil(),
        parent_phrase="oben eine Tasche 60x40x10",
    )

    assert out["teil_id"] == "wuerfel"
    assert out["phrase_idx"] == 3
    assert out["parent_phrase_idx"] == 2


def test_top_level_action_keeps_parent_none():
    agent = _make_agent()
    agent.call_json = MagicMock(return_value={
        "typ": "tasche", "seite": "oben", "parameter_hints": {}
    })
    out = agent.classify(_phrase("oben eine Tasche 60x40x10"), _teil())
    assert out["parent_phrase_idx"] is None


# ── Robustheit: defekte LLM-Outputs ─────────────────────────────────────────


def test_invalid_typ_falls_back_to_unbekannt():
    agent = _make_agent()
    agent.call_json = MagicMock(return_value={
        "typ": "schraubenloch", "seite": "oben", "parameter_hints": {},
    })
    out = agent.classify(_phrase("..."), _teil())
    assert out["typ"] == "unbekannt"


def test_invalid_seite_falls_back_to_oben():
    agent = _make_agent()
    agent.call_json = MagicMock(return_value={
        "typ": "bohrung", "seite": "diagonal", "parameter_hints": {},
    })
    out = agent.classify(_phrase("..."), _teil())
    assert out["seite"] == "oben"


def test_missing_typ_and_seite_use_defaults():
    agent = _make_agent()
    agent.call_json = MagicMock(return_value={})
    out = agent.classify(_phrase("..."), _teil())
    assert out["typ"] == "unbekannt"
    assert out["seite"] == "oben"
    assert out["parameter_hints"] == {}


def test_parameter_hints_non_dict_replaced_with_empty_dict():
    agent = _make_agent()
    agent.call_json = MagicMock(return_value={
        "typ": "bohrung", "seite": "oben", "parameter_hints": "8mm",
    })
    out = agent.classify(_phrase("..."), _teil())
    assert out["parameter_hints"] == {}


def test_llm_exception_yields_default_classification():
    """Wenn der LLM-Call fehlschlaegt, bleibt der Eintrag verwertbar:
    Splitter-Felder erhalten + Defaults fuer LLM-Felder."""
    agent = _make_agent()
    agent.call_json = MagicMock(side_effect=RuntimeError("Ollama down"))

    out = agent.classify(
        _phrase("rechts eine Bohrung 8mm",
                teil_id="wuerfel", phrase_idx=2, parent_phrase_idx=None),
        _teil(),
    )

    assert out["typ"] == "unbekannt"
    assert out["seite"] == "oben"
    assert out["parameter_hints"] == {}
    assert out["beschreibung"] == "rechts eine Bohrung 8mm"
    assert out["teil_id"] == "wuerfel"
    assert out["phrase_idx"] == 2


def test_typ_normalized_to_lowercase_and_trimmed():
    agent = _make_agent()
    agent.call_json = MagicMock(return_value={
        "typ": "  Bohrung  ", "seite": "  Rechts  ",
        "parameter_hints": {},
    })
    out = agent.classify(_phrase("..."), _teil())
    assert out["typ"] == "bohrung"
    assert out["seite"] == "rechts"


# ── Prompt-Building ─────────────────────────────────────────────────────────


def test_prompt_includes_parent_phrase_when_provided():
    agent = _make_agent()
    captured = {}

    def fake_call(prompt, system=""):
        captured["prompt"] = prompt
        return {"typ": "bohrung", "seite": "oben", "parameter_hints": {}}

    agent.call_json = fake_call
    agent.classify(
        _phrase("in der Tasche eine Bohrung 5mm", parent_phrase_idx=0),
        _teil(),
        parent_phrase="oben eine Tasche 60x40x10",
    )

    assert "oben eine Tasche 60x40x10" in captured["prompt"]
    assert "in der Tasche eine Bohrung 5mm" in captured["prompt"]


def test_prompt_marks_top_level_with_keine():
    agent = _make_agent()
    captured = {}

    def fake_call(prompt, system=""):
        captured["prompt"] = prompt
        return {"typ": "tasche", "seite": "oben", "parameter_hints": {}}

    agent.call_json = fake_call
    agent.classify(_phrase("oben eine Tasche 60x40x10"), _teil())

    assert "(keine)" in captured["prompt"]


def test_teil_type_and_params_in_prompt():
    agent = _make_agent()
    captured = {}

    def fake_call(prompt, system=""):
        captured["prompt"] = prompt
        return {"typ": "bohrung", "seite": "oben", "parameter_hints": {}}

    agent.call_json = fake_call
    agent.classify(
        _phrase("..."),
        _teil(type="cylinder", raw_params={"d": 50, "h": 100}),
    )

    assert "cylinder" in captured["prompt"]
    assert "50" in captured["prompt"]
    assert "100" in captured["prompt"]
