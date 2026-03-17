"""
tests/graph/test_pipeline.py — Smoke tests for the Stufe 1 graph.

Goal: verify the graph runs end-to-end with stub nodes.
No real agents, no Ollama, no files — just graph structure.

"Smoke test" = the simplest possible check: does it run without catching fire?
"""

import pytest
from src.graph.pipeline import run, build_graph
from src.graph.state import PipelineState
from src.graph.edges import route_after_executor, route_after_error_router


class TestPipelineSmoke:
    """The graph runs end-to-end with stub nodes."""

    def test_run_returns_state(self):
        """run() must return a dict-like state without raising."""
        state = run("A 30mm cube")
        assert state is not None

    def test_run_has_expected_keys(self):
        """Final state must contain all required fields."""
        state = run("A 30mm cube")
        required_keys = [
            "description", "specification", "blueprint",
            "code", "stl_path", "execution_error", "attempts",
        ]
        for key in required_keys:
            assert key in state, f"Missing key: {key}"

    def test_description_set_from_blueprint(self):
        """After a successful run, description is replaced by blueprint.description."""
        state = run("A bracket with two M4 holes")
        # PipelineRunner replaces description with blueprint.description on success
        assert state["description"] == state["blueprint"]["description"]

    def test_stub_marks_spec_complete(self):
        """Interpreter stub must set is_complete=True."""
        state = run("Test input")
        assert state["is_complete"] is True

    def test_stub_fills_blueprint(self):
        """Planner stub must produce a non-empty blueprint."""
        state = run("Test input")
        assert isinstance(state["blueprint"], dict)
        assert len(state["blueprint"]) > 0

    def test_stub_fills_code(self):
        """Coder stub must produce non-empty code."""
        state = run("Test input")
        assert isinstance(state["code"], str)
        assert len(state["code"]) > 0

    def test_no_errors_on_happy_path(self):
        """With stub nodes, there must be no execution or validation errors."""
        state = run("Test input")
        assert state["execution_error"] == ""
        assert state["validation_error"] == ""

    def test_graph_builds_without_error(self):
        """build_graph() must not raise."""
        graph = build_graph()
        assert graph is not None


class TestRouting:
    """Edge routing functions return the correct targets."""

    def test_route_executor_success(self):
        """No errors → route to validator (not end — validator runs after every success)."""
        state = {
            "execution_error": "",
            "validation_error": "",
            "stl_path": "/tmp/model.stl",
            "attempts": 0,
        }
        assert route_after_executor(state) == "validator"

    def test_route_executor_on_execution_error(self):
        """Execution error → route to error_router."""
        state = {
            "execution_error": "NameError: result is not defined",
            "validation_error": "",
            "stl_path": "",
            "attempts": 0,
        }
        assert route_after_executor(state) == "error_router"

    def test_route_executor_on_validation_error(self):
        """Validation error → route to error_router."""
        state = {
            "execution_error": "",
            "validation_error": "Mesh is not watertight",
            "stl_path": "/tmp/broken.stl",
            "attempts": 0,
        }
        assert route_after_executor(state) == "error_router"

    def test_route_executor_max_attempts(self):
        """After MAX_ATTEMPTS, always route to end regardless of errors."""
        state = {
            "execution_error": "still broken",
            "validation_error": "",
            "stl_path": "",
            "attempts": 6,  # MAX_ATTEMPTS
        }
        assert route_after_executor(state) == "end"

    def test_route_error_router_phase1(self):
        """Phase 1 → Coder fixes its own code."""
        assert route_after_error_router({"phase": 1}) == "coder"

    def test_route_error_router_phase2(self):
        """Phase 2 → CodeFixer diagnoses before Coder retries."""
        assert route_after_error_router({"phase": 2}) == "code_fixer"

    def test_route_error_router_phase3(self):
        """Phase 3 → give up."""
        assert route_after_error_router({"phase": 3}) == "end"
