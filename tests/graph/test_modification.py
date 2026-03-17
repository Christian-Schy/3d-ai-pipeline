"""
tests/graph/test_modification.py — Tests for Stufe 6 iterative editing.
No Ollama needed — agents are mocked.
"""

import pytest
from unittest.mock import patch, MagicMock
from src.graph.edges import route_after_entry_router


# ---------------------------------------------------------------------------
# Routing tests
# ---------------------------------------------------------------------------

class TestEntryRouting:

    def test_fresh_run_routes_to_interpreter(self):
        """No change_description = fresh run → interpreter."""
        state = {"change_description": "", "previous_blueprint": {}}
        assert route_after_entry_router(state) == "interpreter"

    def test_modification_routes_to_task_classifier(self):
        """change_description set = modification → skip interpreter, go to task_classifier (V4)."""
        state = {"change_description": "Increase hole diameter to 5mm"}
        assert route_after_entry_router(state) == "task_classifier"

    def test_empty_string_routes_to_interpreter(self):
        state = {"change_description": ""}
        assert route_after_entry_router(state) == "interpreter"


# ---------------------------------------------------------------------------
# ModificationInterpreterAgent tests
# ---------------------------------------------------------------------------

class TestModificationInterpreter:

    def test_no_previous_blueprint_is_new_request(self):
        """Without previous context, always classify as new request."""
        from src.agents.modification_interpreter import ModificationInterpreterAgent
        agent = ModificationInterpreterAgent()
        state = {"modification": "a cylinder", "previous_blueprint": {}}
        result = agent.classify(state)
        assert result["is_modification"] is False

    def test_modification_detected(self):
        from src.agents.modification_interpreter import ModificationInterpreterAgent
        agent = ModificationInterpreterAgent()
        state = {
            "modification": "Make the hole bigger",
            "previous_blueprint": {
                "description": "Box with hole",
                "root": {"type": "cut",
                         "target": {"type": "box", "x": 30, "y": 30, "z": 10},
                         "tool": {"type": "cylinder", "radius": 2, "height": 12}}
            }
        }
        with patch.object(agent, "call_json", return_value={
            "is_modification": True,
            "change_description": "Increase cylinder hole radius from 2mm to 4mm.",
            "reasoning": "User said 'bigger hole'",
        }):
            result = agent.classify(state)
        assert result["is_modification"] is True
        assert "radius" in result["change_description"].lower()

    def test_new_request_detected(self):
        from src.agents.modification_interpreter import ModificationInterpreterAgent
        agent = ModificationInterpreterAgent()
        state = {
            "modification": "A bracket with two M4 holes",
            "previous_blueprint": {"description": "Box", "root": {"type": "box"}}
        }
        with patch.object(agent, "call_json", return_value={
            "is_modification": False,
            "change_description": "",
            "reasoning": "Completely different object",
        }):
            result = agent.classify(state)
        assert result["is_modification"] is False

    def test_fallback_on_error(self):
        """On connection error: treat as new request (safe default)."""
        from src.agents.modification_interpreter import ModificationInterpreterAgent
        agent = ModificationInterpreterAgent()
        state = {
            "modification": "Make it bigger",
            "previous_blueprint": {"description": "Box", "root": {"type": "box"}}
        }
        with patch.object(agent, "call_json", side_effect=ConnectionRefusedError("down")):
            result = agent.classify(state)
        assert result["is_modification"] is False


# ---------------------------------------------------------------------------
# PlannerAgent patch mode tests
# ---------------------------------------------------------------------------

class TestPlannerPatchMode:

    @pytest.fixture(autouse=True)
    def no_rag(self, monkeypatch):
        monkeypatch.setattr(
            "src.agents.planner.PlannerRAG",
            lambda: MagicMock(build=MagicMock(), enrich_prompt=lambda p, d: p),
        )

    def test_patch_mode_used_when_change_description_set(self):
        """Planner uses PATCH_SYSTEM_PROMPT when change_description is set."""
        from src.agents.planner import PlannerAgent, PATCH_SYSTEM_PROMPT
        agent = PlannerAgent()

        captured_system = []
        def mock_call_json(prompt, system=""):
            captured_system.append(system)
            return {
                "description": "Box with bigger hole",
                "root": {"type": "cut",
                         "target": {"type": "box", "x": 30, "y": 30, "z": 10},
                         "tool": {"type": "cylinder", "radius": 4, "height": 12}},
            }

        with patch.object(agent, "call_json", side_effect=mock_call_json):
            result = agent.run({
                "specification": "Box with hole",
                "change_description": "Increase hole radius to 4mm",
                "previous_blueprint": {
                    "description": "Box with hole",
                    "root": {"type": "box", "x": 30, "y": 30, "z": 10},
                },
                "validator_feedback": "",
                "description": "",
            })

        assert captured_system[0] == PATCH_SYSTEM_PROMPT
        assert "blueprint" in result

    def test_fresh_mode_when_no_change_description(self):
        """Without change_description, Planner uses regular SYSTEM_PROMPT."""
        from src.agents.planner import PlannerAgent, SYSTEM_PROMPT
        agent = PlannerAgent()

        captured_system = []
        def mock_call_json(prompt, system=""):
            captured_system.append(system)
            return {
                "description": "Simple box",
                "root": {"type": "box", "x": 30, "y": 30, "z": 10},
            }

        with patch.object(agent, "call_json", side_effect=mock_call_json):
            result = agent.run({
                "specification": "A 30mm cube",
                "change_description": "",
                "previous_blueprint": {},
                "validator_feedback": "",
                "description": "A 30mm cube",
            })

        assert captured_system[0] == SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# State preservation test
# ---------------------------------------------------------------------------

class TestStatePersistence:

    def test_previous_blueprint_set_after_success(self):
        """validator_node stores blueprint in previous_blueprint on success."""
        from src.graph.nodes import validator_node

        mock_result = MagicMock()
        mock_result.ok = True

        state = {
            "stl_path": "/tmp/model.stl",
            "blueprint": {"description": "Test", "root": {"type": "box"}},
            "semantic_attempts": 0,
            "description": "test",
        }

        from src.agents.validator import ValidatorAgent
        validator_stub = MagicMock()
        validator_stub.check.return_value = mock_result
        with patch("src.graph.nodes.validation_nodes.get_agent", return_value=validator_stub):
            result = validator_node(state)

        assert result["previous_blueprint"] == state["blueprint"]
        assert result["previous_stl_path"] == "/tmp/model.stl"
