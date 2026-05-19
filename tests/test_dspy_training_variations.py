"""Regression tests for hand-curated DSPy variation packs."""

from __future__ import annotations

import sys
from numbers import Number
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DSPY_TRAINING_DIR = PROJECT_ROOT / "data" / "dspy_training"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(DSPY_TRAINING_DIR))


def test_variation_traces_project_to_expected_agents():
    from agent_contracts import project_traces, validate_all
    from variation_traces import TRACES

    assert validate_all(TRACES) == {}
    assert len(project_traces(TRACES, "punctuation")) == 2
    assert len(project_traces(TRACES, "inventar")) == 8
    assert len(project_traces(TRACES, "aktions_klassifizierer")) == 8
    assert len(project_traces(TRACES, "normalizer")) == 5


def test_aktions_klassifizierer_seed_is_trainable():
    from klassifizierer_traces import TRACES as KLASS_TRACES
    from train_dspy import load_aktions_klassifizierer_seed, to_dspy_examples

    raw = load_aktions_klassifizierer_seed()
    assert raw
    assert len(raw) >= 75
    assert len(raw) == len(KLASS_TRACES)

    valid_types = {"tasche", "bohrung", "nut", "fase", "rundung"}
    valid_sides = {"oben", "unten", "rechts", "links", "vorne", "hinten"}
    valid_hints = {
        "durchmesser", "tiefe", "laenge", "breite", "hoehe", "radius",
        "kantenlaenge", "groesse", "rotation_deg", "richtung",
        "bohr_durchmesser", "anzahl", "kreis_durchmesser", "abstand",
        "abstand_kante", "start_offset", "startwinkel",
        "rows", "cols", "rasterabstand", "rasterabstand_x", "rasterabstand_y",
        "abstand_oben", "abstand_unten", "abstand_rechts", "abstand_links",
        "abstand_vorne", "abstand_hinten",
        "kante_oben", "kante_unten", "kante_rechts", "kante_links",
        "kante_vorne", "kante_hinten",
        "versatz_oben", "versatz_unten", "versatz_rechts", "versatz_links",
        "versatz_vorne", "versatz_hinten",
        "anfang_oben", "anfang_unten", "anfang_rechts", "anfang_links",
        "anfang_vorne", "anfang_hinten",
        "ende_oben", "ende_unten", "ende_rechts", "ende_links",
        "ende_vorne", "ende_hinten",
    }
    ids = [entry["id"] for entry in KLASS_TRACES]
    assert len(ids) == len(set(ids))

    seen_types = set()
    seen_sides = set()
    hint_keys = set()
    directions = set()
    parent_cases = 0
    pattern_cases = 0
    adjective_face_cases = 0
    rotations = []
    for trace_entry, entry in zip(KLASS_TRACES, raw):
        phrase = trace_entry["phrase"].lower()
        expected = entry["output"]
        seen_types.add(expected["typ"])
        seen_sides.add(expected["seite"])
        assert expected["typ"] in valid_types
        assert expected["seite"] in valid_sides
        assert isinstance(expected["parameter_hints"], dict)
        hint_keys.update(expected["parameter_hints"])
        for key, value in expected["parameter_hints"].items():
            assert key in valid_hints, trace_entry["id"]
            if key == "richtung":
                assert value in {"x", "y", "z"}, trace_entry["id"]
                directions.add(value)
            else:
                assert isinstance(value, Number) and not isinstance(value, bool)
        if entry["input"]["parent_phrase"] != "(keine)":
            parent_cases += 1
        if any(word in phrase for word in (
            "lochkreis", "eckbohr", "reihe", "loecher"
        )):
            pattern_cases += 1
        if any(word in phrase for word in (
            "rechten seite", "vorderen seite", "oberen flaeche",
            "unterseite", "linken flaeche"
        )):
            adjective_face_cases += 1

    assert seen_types == valid_types
    assert seen_sides == valid_sides
    assert {"abstand_unten", "kante_unten", "versatz_unten"} <= hint_keys
    assert {
        "anzahl", "kreis_durchmesser", "abstand", "abstand_kante",
    } <= hint_keys
    assert directions == {"x", "y", "z"}
    assert parent_cases >= 10
    assert pattern_cases >= 5
    assert adjective_face_cases >= 5
    rotations = [
        entry["output"]["parameter_hints"]["rotation_deg"]
        for entry in raw
        if "rotation_deg" in entry["output"]["parameter_hints"]
    ]
    assert any(value < 0 for value in rotations)
    assert any(value > 0 for value in rotations)

    examples = to_dspy_examples(raw, "aktions_klassifizierer")
    assert examples
    first = examples[0]
    assert set(first.inputs().keys()) == {
        "phrase", "teil_type", "teil_params", "parent_phrase"
    }
    assert getattr(first, "klassifikation")


def test_aktions_klassifizierer_split_contracts_are_trainable():
    from agent_contracts import CONTRACTS, project_traces
    from train_dspy import (
        load_aktions_klassifizierer_seed,
        load_classifier_subagent_seed,
        to_dspy_examples,
    )
    from variation_traces import TRACES as VARIATION_TRACES

    minimum_counts = {
        "hole_classifier": 21,
        "pocket_classifier": 22,
        "slot_classifier": 14,
        "grid_classifier": 12,
        "circular_classifier": 7,
        "linear_classifier": 8,
        "edge_feature_classifier": 10,
    }

    for agent, minimum_count in minimum_counts.items():
        assert agent in CONTRACTS
        assert CONTRACTS[agent].active in {True, False}
        seed_pairs = load_classifier_subagent_seed(agent)
        assert len(seed_pairs) >= minimum_count
        trace_pairs = project_traces(VARIATION_TRACES, agent)
        examples = to_dspy_examples(seed_pairs[:1], agent)
        assert examples
        assert set(examples[0].inputs().keys()) == {
            "phrase", "teil_type", "teil_params", "parent_phrase"
        }
        assert getattr(examples[0], "klassifikation")

        if agent == "grid_classifier":
            grid_keys = {
                key
                for pair in seed_pairs
                for key in pair["output"].get("parameter_hints", {})
            }
            # Both grid arms must be represented: explicit raster
            # (rows/cols/rasterabstand) and corner holes (anzahl/abstand_kante).
            assert {
                "rows", "cols", "rasterabstand",
                "anzahl", "abstand_kante", "durchmesser",
            } <= grid_keys
        if agent == "circular_classifier":
            circular_keys = {
                key
                for pair in seed_pairs
                for key in pair["output"].get("parameter_hints", {})
            }
            assert {"anzahl", "kreis_durchmesser", "durchmesser"} <= circular_keys
        if agent == "linear_classifier":
            linear_keys = {
                key
                for pair in seed_pairs
                for key in pair["output"].get("parameter_hints", {})
            }
            assert {"anzahl", "abstand", "richtung"} <= linear_keys
        if agent == "slot_classifier":
            slot_keys = {
                key
                for pair in seed_pairs
                for key in pair["output"].get("parameter_hints", {})
            }
            assert {"richtung", "rotation_deg"} <= slot_keys
        if agent == "pocket_classifier":
            pocket_keys = {
                key
                for pair in seed_pairs
                for key in pair["output"].get("parameter_hints", {})
            }
            assert {"hoehe", "rotation_deg", "kante_rechts"} <= pocket_keys
        if agent in {"hole_classifier", "pocket_classifier"}:
            assert trace_pairs

    assert sum(
        len(load_classifier_subagent_seed(agent))
        for agent in minimum_counts
    ) == len(load_aktions_klassifizierer_seed())


def test_aktions_klassifizierer_run_trace_expands_per_phrase():
    from train_dspy import extract_aktions_klassifizierer_run_examples

    runs = [{
        "success": True,
        "feedback": "good",
        "agent_traces": [
            {
                "agent": "inventar",
                "output": {
                    "teile": [{
                        "id": "wuerfel",
                        "type": "box",
                        "raw_params": {"x": 100, "y": 100, "z": 100},
                    }],
                },
            },
            {
                "agent": "aktions_klassifizierer",
                "output": {
                    "klassifikationen": [{
                        "typ": "bohrung",
                        "seite": "oben",
                        "beschreibung": "oben eine 8mm bohrung",
                        "teil_id": "wuerfel",
                        "phrase_idx": 0,
                        "parent_phrase_idx": None,
                        "parameter_hints": {"durchmesser": 8},
                    }],
                },
            },
        ],
    }]

    pairs = extract_aktions_klassifizierer_run_examples(runs)

    assert pairs == [{
        "input": {
            "phrase": "oben eine 8mm bohrung",
            "teil_type": "box",
            "teil_params": {"x": 100, "y": 100, "z": 100},
            "parent_phrase": "(keine)",
        },
        "output": {
            "typ": "bohrung",
            "seite": "oben",
            "parameter_hints": {"durchmesser": 8},
        },
        "feedback": "good",
    }]


def test_normalizer_training_contract_uses_runtime_shortform():
    from train_dspy import (
        load_normalizer_seed,
        load_traces,
        to_dspy_examples,
        traces_to_agent_pairs,
    )

    trace_pairs = traces_to_agent_pairs(load_traces(), "normalizer")
    seed_pairs = load_normalizer_seed()
    raw = trace_pairs + seed_pairs
    assert len(trace_pairs) >= 220
    assert len(seed_pairs) >= 21

    valid_types = {
        "bohrung", "lochkreis", "eckbohrungen", "bohrungsreihe",
        "nut", "tasche", "fase", "rundung", "aushoelung",
    }
    valid_sides = {"oben", "unten", "rechts", "links", "vorne", "hinten"}
    valid_param_keys = {
        "durchmesser", "bohr_durchmesser", "tiefe", "kreis_durchmesser",
        "anzahl", "abstand", "abstand_kante", "breite", "laenge",
        "groesse", "radius", "dicke", "drehung", "kanten",
        "rows", "cols", "rasterabstand", "rasterabstand_x", "rasterabstand_y",
        "abstand_oben", "abstand_unten", "abstand_rechts", "abstand_links",
        "abstand_vorne", "abstand_hinten",
        "versatz_oben", "versatz_unten", "versatz_rechts", "versatz_links",
        "versatz_vorne", "versatz_hinten",
        "kante_oben", "kante_unten", "kante_rechts", "kante_links",
        "kante_vorne", "kante_hinten",
    }
    seen_types = set()
    seen_param_keys = set()

    for pair in raw:
        output = pair["output"]
        assert isinstance(output, str)
        assert output.lstrip().startswith("typ:")
        assert not output.lstrip().startswith("{")
        fields = {}
        for line in output.splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
        assert fields.get("typ") in valid_types
        assert fields.get("seite") in valid_sides
        seen_types.add(fields["typ"])
        params = fields.get("parameter", "")
        for part in params.split(","):
            if "=" not in part:
                continue
            key = part.partition("=")[0].strip()
            assert key in valid_param_keys
            seen_param_keys.add(key)

    assert {
        "bohrung", "lochkreis", "eckbohrungen", "bohrungsreihe",
        "nut", "tasche", "fase", "rundung",
    } <= seen_types
    assert {
        "abstand_oben", "abstand_hinten", "versatz_rechts", "versatz_oben",
        "versatz_links", "versatz_unten", "versatz_vorne", "versatz_hinten",
        "kante_oben", "kante_unten", "kante_rechts", "kante_links",
        "kante_vorne", "kante_hinten", "drehung", "dicke",
        "rows", "cols", "rasterabstand",
    } <= seen_param_keys

    examples = to_dspy_examples(raw[:1], "normalizer")
    assert examples
    assert getattr(examples[0], "normalisierung")


def test_platzierer_split_contracts_use_current_schema():
    from agent_contracts import active_agents, project_traces
    from labeler_platzierer_traces import ALL_TRACES

    active = set(active_agents())
    assert "platzierer" not in active
    assert {
        "platzierer_frame",
        "platzierer_alignment",
        "platzierer_anchor",
        "platzierer_offset",
    } <= active

    frame = project_traces(ALL_TRACES, "platzierer_frame")
    alignment = project_traces(ALL_TRACES, "platzierer_alignment")
    anchor = project_traces(ALL_TRACES, "platzierer_anchor")
    offset = project_traces(ALL_TRACES, "platzierer_offset")

    assert len(frame) == len(alignment) == len(offset)
    assert len(frame) >= 17
    assert anchor

    assert frame[0]["output"].splitlines() == [
        "parent: wuerfel",
        "seite: oben",
        "orientierung: 100x20_liegt_auf",
        "anliegende_flaeche: 100x20",
    ]
    assert all("centered" not in p["output"] for p in alignment)
    assert any("kind_punkt: top_left" in p["output"] for p in anchor)
    assert any("kind_punkt: bottom_left" in p["output"] for p in anchor)
    assert any("kind_punkt: bottom_right" in p["output"] for p in anchor)
    assert any(
        "kind_punkt: top_left" in p["output"]
        and "eltern_punkt: bottom_right" in p["output"]
        for p in anchor
    )
    assert any(
        "kind_punkt: bottom_right" in p["output"]
        and "eltern_punkt: top_left" in p["output"]
        for p in anchor
    )
    assert any(
        "obere rechte ecke der platte auf obere rechte ecke" in
        p["input"]["position_sentence"].lower()
        and p["output"] == "ausrichtung: zentriert"
        for p in alignment
    )
    assert any("winkel:" in p["output"] for p in offset)
    assert any("versatz:" in p["output"] for p in offset)


def test_platzierer_split_examples_are_trainable():
    from agent_contracts import project_traces
    from labeler_platzierer_traces import ALL_TRACES
    from train_dspy import to_dspy_examples

    frame_pairs = project_traces(ALL_TRACES, "platzierer_frame")
    frame_examples = to_dspy_examples(frame_pairs[:1], "platzierer_frame")

    assert frame_examples
    assert set(frame_examples[0].inputs().keys()) == {
        "teil_id",
        "teil_type",
        "teil_params",
        "alle_teile",
        "position_sentence",
    }
    assert getattr(frame_examples[0], "frame").startswith("parent:")
