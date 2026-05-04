"""
tests/graph/test_error_loop.py — Tests for the Stufe 3 error loop.

No Ollama needed — agents are mocked where necessary.
"""

import pytest
from unittest.mock import patch
from src.graph.edges import (
    route_after_executor,
    route_after_validator,
    route_after_error_router,
    MAX_ATTEMPTS,
    MAX_SEMANTIC_RETRIES,
)
from src.config.loader import get_config

# Read the live threshold so tests stay in sync when config.yaml changes
_MAX_SEMANTIC = get_config().error_loop.max_semantic_retries
_MAX_ATTEMPTS = get_config().error_loop.max_attempts
from src.agents.code_fixer import CodeFixerAgent


class TestRouteAfterExecutor:
    def test_success_routes_to_validator(self):
        state = {"execution_error": "", "validation_error": "", "stl_path": "/tmp/x.stl", "attempts": 0}
        assert route_after_executor(state) == "validator"

    def test_execution_error_routes_to_error_router(self):
        state = {"execution_error": "NameError", "validation_error": "", "stl_path": "", "attempts": 0}
        assert route_after_executor(state) == "error_router"

    def test_validation_error_routes_to_error_router(self):
        state = {"execution_error": "", "validation_error": "not watertight", "stl_path": "", "attempts": 0}
        assert route_after_executor(state) == "error_router"

    def test_max_attempts_ends_even_with_error(self):
        state = {"execution_error": "still broken", "validation_error": "", "stl_path": "", "attempts": MAX_ATTEMPTS}
        assert route_after_executor(state) == "end"

    def test_one_below_max_still_routes_to_error_router(self):
        state = {"execution_error": "error", "validation_error": "", "stl_path": "", "attempts": MAX_ATTEMPTS - 1}
        assert route_after_executor(state) == "error_router"

    def test_template_mode_execution_error_ends_without_coder(self):
        # Template-mode failures must not trigger the Coder repair loop.
        state = {"execution_error": "NameError", "validation_error": "",
                 "stl_path": "", "attempts": 0, "generation_mode": "template"}
        assert route_after_executor(state) == "end"

    def test_template_mode_geometry_error_ends_without_coder(self):
        state = {"execution_error": "", "validation_error": "STL geometry invalid: not watertight",
                 "stl_path": "", "attempts": 0, "generation_mode": "template"}
        assert route_after_executor(state) == "end"

    def test_llm_mode_still_routes_to_error_router(self):
        # Non-template runs keep the existing repair loop.
        state = {"execution_error": "NameError", "validation_error": "",
                 "stl_path": "", "attempts": 0, "generation_mode": "llm"}
        assert route_after_executor(state) == "error_router"


class TestRouteAfterValidator:
    def test_ok_routes_to_end(self):
        """Empty validator_feedback = validator said OK."""
        state = {"validator_feedback": "", "semantic_attempts": 0}
        assert route_after_validator(state) == "end"

    def test_feedback_routes_to_planner(self):
        """Validator found issue → Planner gets another chance."""
        state = {"validator_feedback": "Missing hole on top face.", "semantic_attempts": 1}
        assert route_after_validator(state) == "planner"

    def test_max_semantic_retries_routes_to_end(self):
        """After max_semantic_retries (from config), give up even with feedback."""
        state = {"validator_feedback": "Still wrong.", "semantic_attempts": _MAX_SEMANTIC}
        assert route_after_validator(state) == "end"

    def test_max_semantic_retries_is_reasonable(self):
        assert 1 <= _MAX_SEMANTIC <= 5


class TestRouteAfterErrorRouter:
    def test_phase1_routes_to_coder(self):
        assert route_after_error_router({"phase": 1}) == "coder"

    def test_phase2_routes_to_code_fixer(self):
        """Phase 2 now goes to CodeFixer first, not directly to Coder."""
        assert route_after_error_router({"phase": 2}) == "code_fixer"

    def test_phase3_routes_to_end(self):
        assert route_after_error_router({"phase": 3}) == "end"


class TestCodeFixerFallback:
    """CodeFixer degrades gracefully when Ollama is unreachable."""

    def _make_state(self) -> dict:
        return {
            "execution_error": "AttributeError: Workplane has no attribute 'cutBlind'",
            "validation_error": "",
            "code": "result = cq.Workplane('XY').box(30,30,30).cutBlind(-5)",
            "blueprint": {"base_shape": "box", "operations": [{"type": "hole"}]},
            "attempts": 3,
            "fix_plan": "",
        }

    def test_returns_fix_plan_key(self):
        agent = CodeFixerAgent()
        with patch.object(agent, "call", return_value=(
            "ROOT_CAUSE: Wrong method name.\n"
            "FIX_PLAN: 1. Use .hole() instead of .cutBlind() for simple holes."
        )):
            result = agent.diagnose(self._make_state())
        assert "fix_plan" in result
        assert len(result["fix_plan"]) > 0

    def test_fallback_on_connection_error(self):
        agent = CodeFixerAgent()
        with patch.object(agent, "call", side_effect=ConnectionRefusedError("Ollama down")):
            result = agent.diagnose(self._make_state())
        assert "fix_plan" in result
        assert len(result["fix_plan"]) > 0  # fallback text, not empty


class TestLoopTermination:
    def test_max_attempts_is_reasonable(self):
        assert 4 <= MAX_ATTEMPTS <= 10

    def test_loop_always_ends_at_max(self):
        for attempt in range(MAX_ATTEMPTS, MAX_ATTEMPTS + 3):
            state = {"execution_error": "error", "validation_error": "", "stl_path": "", "attempts": attempt}
            assert route_after_executor(state) == "end"

    def test_semantic_loop_always_ends_at_max(self):
        for sa in range(_MAX_SEMANTIC, _MAX_SEMANTIC + 3):
            state = {"validator_feedback": "still wrong", "semantic_attempts": sa}
            assert route_after_validator(state) == "end"
