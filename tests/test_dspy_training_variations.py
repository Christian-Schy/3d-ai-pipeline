"""Regression tests for hand-curated DSPy variation packs."""

from __future__ import annotations

import sys
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
    from train_dspy import load_aktions_klassifizierer_seed, to_dspy_examples

    raw = load_aktions_klassifizierer_seed()
    assert raw

    examples = to_dspy_examples(raw, "aktions_klassifizierer")
    assert examples
    first = examples[0]
    assert set(first.inputs().keys()) == {
        "phrase", "teil_type", "teil_params", "parent_phrase"
    }
    assert getattr(first, "klassifikation")


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
