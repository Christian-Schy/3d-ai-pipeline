"""tests/agents/test_aktions_chain_nodes.py — Node-Wrapper-Tests fuer
die Per-Aktion-Kette (ADR 0003 Stufe 5a).

Drei Nodes:
  - aktions_splitter_node:        deterministisch
  - aktions_klassifizierer_node:  LLM-Loop (Klassifizierer wird gemockt)
  - aktions_aggregator_node:      deterministisch

Tests pruefen Wiring (Input aus state, Output in state, agent_traces),
nicht die Tool-/Agent-Internals (die haben eigene Tests).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def fresh_state() -> dict:
    """Minimal-Pipeline-State fuer einen Run."""
    return {
        "specification": (
            "200mm wuerfel, "
            "rechts eine Tasche 60x40x10 in der Tasche eine Bohrung 8mm 10 tief"
        ),
        "inventar": {
            "teil_count": 1,
            "teile": [{
                "id": "wuerfel", "type": "box",
                "raw_params": {"x": 200, "y": 200, "z": 200},
                "beschreibung": "200mm wuerfel",
            }],
            "aktionen": [],
        },
        "agent_traces": [],
    }


# ── aktions_splitter_node ──────────────────────────────────────────────


def test_splitter_node_writes_phrases_and_trace(fresh_state):
    from src.graph.nodes import aktions_splitter_node

    out = aktions_splitter_node(fresh_state)

    assert "aktions_phrases" in out
    phrases = out["aktions_phrases"]
    # Spec hat 1 Tasche + 1 nested Bohrung → 2 Phrasen
    assert len(phrases) == 2
    assert phrases[0]["parent_phrase_idx"] is None
    assert phrases[1]["parent_phrase_idx"] == 0

    assert len(out["agent_traces"]) == 1
    tr = out["agent_traces"][0]
    assert tr["agent"] == "aktions_splitter"
    assert "duration_ms" in tr


def test_splitter_node_skips_when_no_spec(fresh_state):
    from src.graph.nodes import aktions_splitter_node
    fresh_state["specification"] = ""
    fresh_state["description"] = ""

    out = aktions_splitter_node(fresh_state)

    assert out["aktions_phrases"] == []
    assert out["agent_traces"][0]["output"]["skipped"] is True


def test_splitter_node_skips_when_no_teile(fresh_state):
    from src.graph.nodes import aktions_splitter_node
    fresh_state["inventar"] = {"teile": []}

    out = aktions_splitter_node(fresh_state)

    assert out["aktions_phrases"] == []
    assert out["agent_traces"][0]["output"]["skipped"] is True


def test_splitter_node_falls_back_to_description_when_specification_missing(fresh_state):
    from src.graph.nodes import aktions_splitter_node
    fresh_state["description"] = fresh_state["specification"]
    del fresh_state["specification"]

    out = aktions_splitter_node(fresh_state)
    assert len(out["aktions_phrases"]) == 2


# ── aktions_klassifizierer_node ────────────────────────────────────────


def _patch_klassifizierer(monkeypatch, side_effect=None, return_value=None):
    """Replace AktionsKlassifizierer instance used by the node with a stub."""
    from src.graph.nodes import _registry
    from src.agents.aktions_klassifizierer import AktionsKlassifizierer
    import src.graph.nodes.planning_action_nodes as action_nodes

    # These wiring tests target the monolithic fallback path. Pin the route
    # config locally so global classifier-subagent flags cannot make them call
    # real subagents.
    monkeypatch.setattr(action_nodes, "get_config", lambda: _fake_classifier_config())

    stub = MagicMock(spec=AktionsKlassifizierer)
    if side_effect is not None:
        stub.classify.side_effect = side_effect
    elif return_value is not None:
        stub.classify.return_value = return_value
    stub._last_raw_response = "RAW"

    _registry.get_agent.cache_clear()
    monkeypatch.setattr(
        _registry, "get_agent",
        lambda cls: stub if cls is AktionsKlassifizierer else cls(),
    )
    # Also patch the planning_nodes-imported reference
    import src.graph.nodes.planning_nodes as planning
    monkeypatch.setattr(planning, "get_agent",
        lambda cls: stub if cls is AktionsKlassifizierer else cls(),
    )
    return stub


def _fake_classifier_config(**flags):
    defaults = {
        "hole_enabled": False,
        "pocket_enabled": False,
        "slot_enabled": False,
        "grid_enabled": False,
        "circular_enabled": False,
        "linear_enabled": False,
        "edge_feature_enabled": False,
    }
    defaults.update(flags)
    return SimpleNamespace(
        classifier_subagents=SimpleNamespace(**defaults),
        models=SimpleNamespace(
            aktions_klassifizierer="test-classifier",
            inventar="test-inventar",
        ),
    )


def test_detect_classifier_subagent_routes_only_unambiguous_phrases():
    from src.graph.nodes.planning_action_nodes import detect_classifier_subagent

    assert detect_classifier_subagent("oben eine 8mm bohrung") == "hole_classifier"
    assert detect_classifier_subagent("oben eine tasche 20x10x5") == "pocket_classifier"
    assert detect_classifier_subagent("rechts eine nut 5x3 entlang z") == "slot_classifier"
    assert detect_classifier_subagent("oben lochkreis 60mm mit 6 bohrungen") == "circular_classifier"
    assert detect_classifier_subagent("oben ein lochmuster 4x3 rasterabstand 25mm") == "grid_classifier"
    assert detect_classifier_subagent("oben 4 eckbohrungen 20mm von den kanten") == "grid_classifier"
    assert detect_classifier_subagent("oben eine bohrungsreihe entlang x abstand 20mm") == "linear_classifier"
    assert detect_classifier_subagent("oben eine fase 2mm") == "edge_feature_classifier"
    assert detect_classifier_subagent("oben eine tasche mit bohrung") is None


def test_klassifizierer_node_classifies_each_phrase(monkeypatch, fresh_state):
    from src.graph.nodes import aktions_klassifizierer_node

    fresh_state["aktions_phrases"] = [
        {"phrase": "rechts eine Tasche 60x40x10",
         "teil_id": "wuerfel", "phrase_idx": 0, "parent_phrase_idx": None},
        {"phrase": "in der Tasche eine Bohrung 8mm 10 tief",
         "teil_id": "wuerfel", "phrase_idx": 1, "parent_phrase_idx": 0},
    ]

    classifications = [
        {"typ": "tasche", "seite": "rechts",
         "beschreibung": "rechts eine Tasche 60x40x10",
         "teil_id": "wuerfel", "phrase_idx": 0, "parent_phrase_idx": None,
         "parameter_hints": {"laenge": 60, "breite": 40, "tiefe": 10}},
        {"typ": "bohrung", "seite": "rechts",
         "beschreibung": "in der Tasche eine Bohrung 8mm 10 tief",
         "teil_id": "wuerfel", "phrase_idx": 1, "parent_phrase_idx": 0,
         "parameter_hints": {"durchmesser": 8, "tiefe": 10}},
    ]
    stub = _patch_klassifizierer(monkeypatch, side_effect=classifications)

    out = aktions_klassifizierer_node(fresh_state)

    assert len(out["aktions_klassifikationen"]) == 2
    assert out["aktions_klassifikationen"][0]["typ"] == "tasche"
    assert out["aktions_klassifikationen"][1]["typ"] == "bohrung"
    assert stub.classify.call_count == 2


def test_klassifizierer_node_uses_fallback_when_subagent_disabled(monkeypatch, fresh_state):
    from src.graph.nodes import aktions_klassifizierer_node
    import src.graph.nodes.planning_action_nodes as action_nodes

    monkeypatch.setattr(action_nodes, "get_config", lambda: _fake_classifier_config())
    fresh_state["aktions_phrases"] = [
        {"phrase": "oben eine 8mm bohrung",
         "teil_id": "wuerfel", "phrase_idx": 0, "parent_phrase_idx": None},
    ]
    stub = _patch_klassifizierer(monkeypatch, return_value={
        "typ": "bohrung", "seite": "oben",
        "beschreibung": "oben eine 8mm bohrung",
        "teil_id": "wuerfel", "phrase_idx": 0, "parent_phrase_idx": None,
        "parameter_hints": {"durchmesser": 8},
    })

    out = aktions_klassifizierer_node(fresh_state)

    assert stub.classify.call_count == 1
    routes = out["agent_traces"][0]["output"]["routes"]
    assert routes["hole_classifier_disabled"] == 1
    assert routes["fallback"] == 1


def test_klassifizierer_node_routes_to_enabled_subagent(monkeypatch, fresh_state):
    from src.agents.aktions_klassifizierer import AktionsKlassifizierer
    from src.agents.classifier_sub_agents import HoleClassifier
    from src.graph.nodes import aktions_klassifizierer_node
    from src.graph.nodes import _registry
    import src.graph.nodes.planning_action_nodes as action_nodes

    monkeypatch.setattr(
        action_nodes, "get_config",
        lambda: _fake_classifier_config(hole_enabled=True),
    )
    fresh_state["aktions_phrases"] = [
        {"phrase": "oben eine 8mm bohrung",
         "teil_id": "wuerfel", "phrase_idx": 0, "parent_phrase_idx": None},
    ]

    fallback_stub = MagicMock(spec=AktionsKlassifizierer)
    fallback_stub._last_raw_response = "FALLBACK"
    hole_stub = MagicMock(spec=HoleClassifier)
    hole_stub._last_raw_response = "HOLE"
    hole_stub.classify.return_value = {
        "typ": "bohrung", "seite": "oben",
        "beschreibung": "oben eine 8mm bohrung",
        "teil_id": "wuerfel", "phrase_idx": 0, "parent_phrase_idx": None,
        "parameter_hints": {"durchmesser": 8},
    }

    _registry.get_agent.cache_clear()
    monkeypatch.setattr(
        _registry,
        "get_agent",
        lambda cls: (
            fallback_stub if cls is AktionsKlassifizierer
            else hole_stub if cls is HoleClassifier
            else cls()
        ),
    )

    out = aktions_klassifizierer_node(fresh_state)

    assert hole_stub.classify.call_count == 1
    assert fallback_stub.classify.call_count == 0
    routes = out["agent_traces"][0]["output"]["routes"]
    assert routes["hole_classifier"] == 1


def test_klassifizierer_node_falls_back_when_subagent_fails(monkeypatch, fresh_state):
    from src.agents.aktions_klassifizierer import AktionsKlassifizierer
    from src.agents.classifier_sub_agents import HoleClassifier
    from src.graph.nodes import aktions_klassifizierer_node
    from src.graph.nodes import _registry
    import src.graph.nodes.planning_action_nodes as action_nodes

    monkeypatch.setattr(
        action_nodes, "get_config",
        lambda: _fake_classifier_config(hole_enabled=True),
    )
    fresh_state["aktions_phrases"] = [
        {"phrase": "oben eine 8mm bohrung",
         "teil_id": "wuerfel", "phrase_idx": 0, "parent_phrase_idx": None},
    ]

    fallback_stub = MagicMock(spec=AktionsKlassifizierer)
    fallback_stub._last_raw_response = "FALLBACK"
    fallback_stub.classify.return_value = {
        "typ": "bohrung", "seite": "oben",
        "beschreibung": "oben eine 8mm bohrung",
        "teil_id": "wuerfel", "phrase_idx": 0, "parent_phrase_idx": None,
        "parameter_hints": {"durchmesser": 8},
    }
    hole_stub = MagicMock(spec=HoleClassifier)
    hole_stub._last_raw_response = "HOLE"
    hole_stub.classify.side_effect = RuntimeError("subagent unavailable")

    _registry.get_agent.cache_clear()
    monkeypatch.setattr(
        _registry,
        "get_agent",
        lambda cls: (
            fallback_stub if cls is AktionsKlassifizierer
            else hole_stub if cls is HoleClassifier
            else cls()
        ),
    )

    out = aktions_klassifizierer_node(fresh_state)

    assert hole_stub.classify.call_count == 1
    assert fallback_stub.classify.call_count == 1
    routes = out["agent_traces"][0]["output"]["routes"]
    assert routes["fallback_after_subagent_error"] == 1


def test_klassifizierer_node_passes_parent_phrase_for_nested(monkeypatch, fresh_state):
    """Nested children must receive the parent's phrase as context so the
    classifier can inherit `seite`."""
    from src.graph.nodes import aktions_klassifizierer_node

    fresh_state["aktions_phrases"] = [
        {"phrase": "oben eine Tasche", "teil_id": "wuerfel",
         "phrase_idx": 0, "parent_phrase_idx": None},
        {"phrase": "in der Tasche eine Bohrung", "teil_id": "wuerfel",
         "phrase_idx": 1, "parent_phrase_idx": 0},
    ]
    classifications = [
        {"typ": "tasche", "seite": "oben",
         "beschreibung": "oben eine Tasche",
         "teil_id": "wuerfel", "phrase_idx": 0, "parent_phrase_idx": None,
         "parameter_hints": {}},
        {"typ": "bohrung", "seite": "oben",
         "beschreibung": "in der Tasche eine Bohrung",
         "teil_id": "wuerfel", "phrase_idx": 1, "parent_phrase_idx": 0,
         "parameter_hints": {}},
    ]
    stub = _patch_klassifizierer(monkeypatch, side_effect=classifications)

    aktions_klassifizierer_node(fresh_state)

    # Erster Call: kein parent_phrase
    first_kwargs = stub.classify.call_args_list[0].kwargs
    assert first_kwargs.get("parent_phrase") is None
    # Zweiter Call: parent_phrase = beschreibung der ersten Klassifikation
    second_kwargs = stub.classify.call_args_list[1].kwargs
    assert second_kwargs.get("parent_phrase") == "oben eine Tasche"


def test_klassifizierer_node_inherits_section_side(monkeypatch, fresh_state):
    """Section headers like 'rechts (...):' define the face for following
    local-position phrases in the same semicolon list."""
    from src.graph.nodes import aktions_klassifizierer_node

    fresh_state["aktions_phrases"] = [
        {"phrase": "oben (also auf der 200x100 flaeche): oben rechts eine Bohrung",
         "teil_id": "wuerfel", "phrase_idx": 0, "parent_phrase_idx": None},
        {"phrase": "unten links eine Bohrung",
         "teil_id": "wuerfel", "phrase_idx": 1, "parent_phrase_idx": None},
        {"phrase": "rechts (also auf der 100x80 flaeche): oben rechts eine Bohrung",
         "teil_id": "wuerfel", "phrase_idx": 2, "parent_phrase_idx": None},
        {"phrase": "nach unten 15mm und nach links 20mm versetzt eine Bohrung",
         "teil_id": "wuerfel", "phrase_idx": 3, "parent_phrase_idx": None},
    ]
    classifications = [
        {"typ": "bohrung", "seite": "oben",
         "beschreibung": fresh_state["aktions_phrases"][0]["phrase"],
         "teil_id": "wuerfel", "phrase_idx": 0, "parent_phrase_idx": None,
         "parameter_hints": {}},
        {"typ": "bohrung", "seite": "unten",
         "beschreibung": fresh_state["aktions_phrases"][1]["phrase"],
         "teil_id": "wuerfel", "phrase_idx": 1, "parent_phrase_idx": None,
         "parameter_hints": {}},
        {"typ": "bohrung", "seite": "rechts",
         "beschreibung": fresh_state["aktions_phrases"][2]["phrase"],
         "teil_id": "wuerfel", "phrase_idx": 2, "parent_phrase_idx": None,
         "parameter_hints": {}},
        {"typ": "bohrung", "seite": "oben",
         "beschreibung": fresh_state["aktions_phrases"][3]["phrase"],
         "teil_id": "wuerfel", "phrase_idx": 3, "parent_phrase_idx": None,
         "parameter_hints": {}},
    ]
    _patch_klassifizierer(monkeypatch, side_effect=classifications)

    out = aktions_klassifizierer_node(fresh_state)

    assert [k["seite"] for k in out["aktions_klassifikationen"]] == [
        "oben", "oben", "rechts", "rechts",
    ]


def test_klassifizierer_node_skips_phrase_with_unknown_teil(monkeypatch, fresh_state):
    from src.graph.nodes import aktions_klassifizierer_node

    fresh_state["aktions_phrases"] = [
        {"phrase": "rechts eine Bohrung 8mm", "teil_id": "ghost",
         "phrase_idx": 0, "parent_phrase_idx": None},
        {"phrase": "oben eine Tasche", "teil_id": "wuerfel",
         "phrase_idx": 0, "parent_phrase_idx": None},
    ]
    stub = _patch_klassifizierer(monkeypatch, return_value={
        "typ": "tasche", "seite": "oben", "beschreibung": "oben eine Tasche",
        "teil_id": "wuerfel", "phrase_idx": 0, "parent_phrase_idx": None,
        "parameter_hints": {},
    })

    out = aktions_klassifizierer_node(fresh_state)

    # Ghost-Phrase wurde uebersprungen, nur die mit gueltigem teil_id durch
    assert len(out["aktions_klassifikationen"]) == 1
    assert stub.classify.call_count == 1


def test_klassifizierer_node_handles_classify_exception(monkeypatch, fresh_state):
    """Wenn ein einzelner classify-Call wirft, geht der Loop weiter und der
    Rest wird trotzdem klassifiziert."""
    from src.graph.nodes import aktions_klassifizierer_node

    fresh_state["aktions_phrases"] = [
        {"phrase": "p0", "teil_id": "wuerfel",
         "phrase_idx": 0, "parent_phrase_idx": None},
        {"phrase": "p1", "teil_id": "wuerfel",
         "phrase_idx": 1, "parent_phrase_idx": None},
    ]
    side_effect = [
        RuntimeError("ollama ate it"),
        {"typ": "bohrung", "seite": "oben", "beschreibung": "p1",
         "teil_id": "wuerfel", "phrase_idx": 1, "parent_phrase_idx": None,
         "parameter_hints": {}},
    ]
    _patch_klassifizierer(monkeypatch, side_effect=side_effect)

    out = aktions_klassifizierer_node(fresh_state)
    assert len(out["aktions_klassifikationen"]) == 1
    assert out["aktions_klassifikationen"][0]["beschreibung"] == "p1"


def test_klassifizierer_node_skips_when_no_phrases(monkeypatch, fresh_state):
    from src.graph.nodes import aktions_klassifizierer_node
    fresh_state["aktions_phrases"] = []
    _patch_klassifizierer(monkeypatch, return_value={})

    out = aktions_klassifizierer_node(fresh_state)
    assert out["aktions_klassifikationen"] == []
    assert out["agent_traces"][0]["output"]["skipped"] is True


# ── aktions_aggregator_node ────────────────────────────────────────────


def test_aggregator_node_builds_teil_definitionen(fresh_state):
    """Wiring-Test: Features rein, teil_definitionen raus.
    Inhaltliche Korrektheit testet test_aktions_aggregator.py."""
    from src.graph.nodes import aktions_aggregator_node

    fresh_state["aktions_features"] = [
        {
            "id": "tasche_rechts_0", "type": "pocket_rect",
            "params": {"x": 60, "y": 40, "depth": 10},
            "position": {"side": "rechts"},
            "operation": "subtract", "parent": "wuerfel",
            "_teil_id": "wuerfel", "_phrase_idx": 0,
            "_parent_phrase_idx": None,
        },
        {
            "id": "bohrung_rechts_1", "type": "hole_single",
            "params": {"diameter": 8, "depth": 10},
            "position": {"side": "rechts"},
            "operation": "subtract", "parent": "wuerfel",
            "_teil_id": "wuerfel", "_phrase_idx": 1,
            "_parent_phrase_idx": 0,
        },
    ]

    out = aktions_aggregator_node(fresh_state)

    assert "teil_definitionen" in out
    tds = out["teil_definitionen"]
    assert len(tds) == 1
    assert tds[0]["id"] == "wuerfel"
    feats = tds[0]["features"]
    assert len(feats) == 2
    # Marker stripped
    assert "_teil_id" not in feats[0]
    # Nested parent resolved
    assert feats[1]["parent"] == "tasche_rechts_0"

    assert out["agent_traces"][0]["agent"] == "aktions_aggregator"


def test_aggregator_node_with_no_features_emits_empty_teil_def(fresh_state):
    from src.graph.nodes import aktions_aggregator_node
    fresh_state["aktions_features"] = []

    out = aktions_aggregator_node(fresh_state)
    assert len(out["teil_definitionen"]) == 1
    assert out["teil_definitionen"][0]["features"] == []
