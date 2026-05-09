"""Tests for shared pipeline run success classification."""

from src.graph.run_status import failure_reason, has_blueprint_content, is_successful_state


def test_success_requires_stl_and_blueprint_content():
    state = {
        "stl_path": "/tmp/model.stl",
        "blueprint": {"features": {"root": {"type": "box"}}},
        "execution_error": "",
        "validation_error": "",
        "validator_feedback": "",
        "coordinate_errors_unresolved": False,
    }

    assert has_blueprint_content(state) is True
    assert is_successful_state(state) is True
    assert failure_reason(state) == ""


def test_empty_blueprint_is_not_success_even_with_stl():
    state = {
        "stl_path": "/tmp/model.stl",
        "blueprint": {},
        "execution_error": "",
        "validation_error": "",
        "validator_feedback": "",
        "coordinate_errors_unresolved": False,
    }

    assert is_successful_state(state) is False
    assert failure_reason(state) == "No blueprint produced"


def test_unresolved_coordinate_errors_block_success():
    state = {
        "stl_path": "/tmp/model.stl",
        "blueprint": {"features": {"root": {"type": "box"}}},
        "execution_error": "",
        "validation_error": "",
        "validator_feedback": "",
        "coordinate_errors_unresolved": True,
        "coordinate_validation_issues": "feature outside parent bounds",
    }

    assert is_successful_state(state) is False
    assert failure_reason(state) == "feature outside parent bounds"
