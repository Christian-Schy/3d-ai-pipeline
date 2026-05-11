"""Tests for ADR-0006 classifier sub-agent code path."""

from unittest.mock import MagicMock


def _phrase(phrase: str, **kwargs):
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


def test_sub_agent_registry_builds_all_agents():
    from src.agents.classifier_sub_agents import (
        CLASSIFIER_SUB_AGENT_CLASSES,
        build_classifier_sub_agent,
    )

    assert set(CLASSIFIER_SUB_AGENT_CLASSES) == {
        "hole_classifier",
        "pocket_classifier",
        "slot_classifier",
        "pattern_classifier",
        "edge_feature_classifier",
    }
    for name in CLASSIFIER_SUB_AGENT_CLASSES:
        assert build_classifier_sub_agent(name).name == name


def test_hole_classifier_forces_type_and_cleans_hints():
    from src.agents.classifier_sub_agents import HoleClassifier

    agent = HoleClassifier()
    agent.call_json = MagicMock(return_value={
        "typ": "tasche",
        "seite": "rechts",
        "parameter_hints": {
            "durchmesser": "8mm",
            "tiefe": 10,
            "laenge": 99,
        },
    })

    out = agent.classify(_phrase("rechts eine 8mm bohrung 10 tief"), _teil())

    assert out["typ"] == "bohrung"
    assert out["seite"] == "rechts"
    assert out["parameter_hints"] == {"durchmesser": 8, "tiefe": 10}
    assert out["beschreibung"] == "rechts eine 8mm bohrung 10 tief"


def test_slot_classifier_keeps_axis_hint_as_direction():
    from src.agents.classifier_sub_agents import SlotClassifier

    agent = SlotClassifier()
    agent.call_json = MagicMock(return_value={
        "typ": "nut",
        "seite": "oben",
        "parameter_hints": {
            "breite": 5,
            "tiefe": "3",
            "richtung": "Y-Achse",
        },
    })

    out = agent.classify(_phrase("oben eine nut 5x3 entlang y-achse"), _teil())

    assert out["typ"] == "nut"
    assert out["parameter_hints"] == {
        "breite": 5,
        "tiefe": 3,
        "richtung": "y",
    }


def test_pattern_classifier_allows_pattern_specific_hints():
    from src.agents.classifier_sub_agents import PatternClassifier

    agent = PatternClassifier()
    agent.call_json = MagicMock(return_value={
        "typ": "bohrung",
        "seite": "oben",
        "parameter_hints": {
            "anzahl": 6,
            "kreis_durchmesser": 60,
            "durchmesser": 10,
            "richtung": "x",
        },
    })

    out = agent.classify(
        _phrase("oben lochkreis 60mm mit 6 bohrungen je 10mm"),
        _teil(),
    )

    assert out["typ"] == "bohrung"
    assert out["parameter_hints"] == {
        "anzahl": 6,
        "kreis_durchmesser": 60,
        "durchmesser": 10,
        "richtung": "x",
    }


def test_edge_feature_classifier_falls_back_from_phrase_when_typ_invalid():
    from src.agents.classifier_sub_agents import EdgeFeatureClassifier

    agent = EdgeFeatureClassifier()
    agent.call_json = MagicMock(return_value={
        "typ": "bohrung",
        "seite": "diagonal",
        "parameter_hints": {"radius": "2mm", "durchmesser": 10},
    })

    out = agent.classify(_phrase("oben eine rundung radius 2mm"), _teil())

    assert out["typ"] == "rundung"
    assert out["seite"] == "oben"
    assert out["parameter_hints"] == {"radius": 2}


def test_sub_agent_prompt_includes_parent_phrase_and_part_context():
    from src.agents.classifier_sub_agents import PocketClassifier

    agent = PocketClassifier()
    captured = {}

    def fake_call(prompt, system=""):
        captured["prompt"] = prompt
        captured["system"] = system
        return {
            "typ": "tasche",
            "seite": "oben",
            "parameter_hints": {"laenge": 20, "breite": 10, "tiefe": 4},
        }

    agent.call_json = fake_call
    agent.classify(
        _phrase("darin eine tasche 20x10x4", parent_phrase_idx=0),
        _teil(raw_params={"x": 80, "y": 60, "z": 20}),
        parent_phrase="oben eine tasche 60x40x10",
    )

    assert "oben eine tasche 60x40x10" in captured["prompt"]
    assert "darin eine tasche 20x10x4" in captured["prompt"]
    assert "80" in captured["prompt"]
    assert "Immer \"tasche\"" in captured["system"]
