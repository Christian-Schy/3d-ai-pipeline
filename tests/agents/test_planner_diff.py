"""
tests/agents/test_planner_diff.py — Tests für PlannerAgent._apply_diff
und den neuen Patch-Modus.

Kein Ollama, kein RAG — _apply_diff ist pure Python.
"""

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def mock_rag(monkeypatch):
    """Block sentence-transformers from loading by mocking at the module level.

    sentence-transformers loads its 80MB model when BaseRAG.__init__ runs.
    We patch both the import location and the usage location so no real
    RAG object is ever instantiated during tests.
    """
    from unittest.mock import MagicMock
    fake_rag = MagicMock()
    fake_rag.return_value.query.return_value = ""
    fake_rag.return_value.build.return_value = None
    fake_rag.return_value.enrich_prompt.side_effect = lambda prompt, desc: prompt
    # Patch both: where it's defined and where it's imported into planner
    monkeypatch.setattr("src.rag.planner_rag.PlannerRAG", fake_rag)
    monkeypatch.setattr("src.agents.planner.PlannerRAG", fake_rag)


class TestApplyDiff:
    """_apply_diff patcht einen Blueprint anhand eines LLM-Diffs."""

    def get_agent(self):
        from src.agents.planner import PlannerAgent
        return PlannerAgent()

    def base_blueprint(self):
        return {
            "description": "30mm cube with 8mm hole",
            "root": {
                "type": "cut",
                "target": {"type": "box", "x": 30, "y": 30, "z": 30},
                "tool": {"type": "cylinder", "radius": 4.0, "height": 32.0},
            }
        }

    def test_simple_value_change(self):
        agent = self.get_agent()
        bp = self.base_blueprint()
        diff = {
            "changes": [{"path": "root.tool.radius", "old_value": 4.0, "new_value": 6.0}],
            "description": "30mm cube with 12mm hole"
        }
        result, applied = agent._apply_diff(bp, diff)
        assert applied >= 1
        assert result["root"]["tool"]["radius"] == 6.0

    def test_description_updated_from_diff(self):
        agent = self.get_agent()
        bp = self.base_blueprint()
        diff = {
            "changes": [{"path": "root.tool.radius", "new_value": 6.0}],
            "description": "30mm cube with 12mm hole"
        }
        result, applied = agent._apply_diff(bp, diff)
        assert result["description"] == "30mm cube with 12mm hole"

    def test_description_fallback_when_missing(self):
        agent = self.get_agent()
        bp = self.base_blueprint()
        diff = {
            "changes": [{"path": "root.tool.radius", "new_value": 6.0}],
        }
        result, applied = agent._apply_diff(bp, diff, change_hint="make hole bigger")
        assert "make hole bigger" in result["description"]

    def test_multiple_changes(self):
        agent = self.get_agent()
        bp = self.base_blueprint()
        diff = {
            "changes": [
                {"path": "root.tool.radius", "new_value": 6.0},
                {"path": "root.tool.height", "new_value": 35.0},
            ]
        }
        result, applied = agent._apply_diff(bp, diff)
        assert applied >= 2
        assert result["root"]["tool"]["radius"] == 6.0
        assert result["root"]["tool"]["height"] == 35.0

    def test_invalid_path_is_skipped(self):
        """Ein ungültiger Pfad darf den Rest nicht blockieren."""
        agent = self.get_agent()
        bp = self.base_blueprint()
        diff = {
            "changes": [
                {"path": "root.nonexistent.value", "new_value": 99},
                {"path": "root.tool.radius", "new_value": 5.0},
            ]
        }
        result, applied = agent._apply_diff(bp, diff)
        # Der gültige Change wird trotzdem angewendet
        assert result["root"]["tool"]["radius"] == 5.0

    def test_empty_diff_returns_false(self):
        agent = self.get_agent()
        bp = self.base_blueprint()
        diff = {"changes": []}
        result, applied = agent._apply_diff(bp, diff)
        assert applied == 0

    def test_original_blueprint_not_mutated(self):
        """_apply_diff macht deepcopy — das Original bleibt unverändert."""
        agent = self.get_agent()
        bp = self.base_blueprint()
        original_radius = bp["root"]["tool"]["radius"]
        diff = {"changes": [{"path": "root.tool.radius", "new_value": 6.0}]}
        agent._apply_diff(bp, diff)
        assert bp["root"]["tool"]["radius"] == original_radius


class TestPlannerReviseMode:
    """Revise-Mode hat höchste Priorität — wird vor Patch-Mode geprüft.

    Hintergrund: validator_feedback bleibt im State nachdem ein Modify-Run
    scheitert. Ohne explizite Priorität würde change_description + previous_blueprint
    den Patch-Zweig triggern — der dann strukturelle Fehler nicht beheben kann.
    """

    def test_revise_mode_takes_priority_over_patch(self):
        """feedback gesetzt → Revise-Mode, auch wenn change_description vorhanden."""
        from src.agents.planner import PlannerAgent, SYSTEM_PROMPT
        agent = PlannerAgent()

        captured = {}
        def fake_call_json(prompt, system=None):
            captured["system"] = system
            return {
                "description": "Fixed box",
                "root": {"type": "box", "x": 30, "y": 30, "z": 30},
            }

        with patch.object(agent, "call_json", side_effect=fake_call_json):
            agent.run({
                "specification": "30mm cube",
                "validator_feedback": "Model is inside-out",
                "change_description": "increase radius",  # also set — must be ignored
                "previous_blueprint": {"description": "old", "root": {"type": "box"}},
                "description": "30mm cube",
            })

        # Must use the full SYSTEM_PROMPT (revise), not PATCH_SYSTEM_PROMPT
        assert captured.get("system") == SYSTEM_PROMPT

    def test_revise_mode_uses_full_system_prompt(self):
        """Revise-Mode enriched prompt enthält Feedback-Text."""
        from src.agents.planner import PlannerAgent
        agent = PlannerAgent()

        captured_prompts = []
        def fake_call_json(prompt, system=None):
            captured_prompts.append(prompt)
            return {
                "description": "Fixed",
                "root": {"type": "box", "x": 10, "y": 10, "z": 10},
            }

        feedback = "The hole should be a cut, not a union"
        with patch.object(agent, "call_json", side_effect=fake_call_json):
            agent.run({
                "specification": "Box with hole",
                "validator_feedback": feedback,
                "change_description": "",
                "previous_blueprint": {},
                "description": "Box with hole",
            })

        assert len(captured_prompts) == 1
        assert feedback in captured_prompts[0]

    def test_revise_mode_uses_smaller_model(self):
        """Revise-Mode schaltet auf planner_revise-Modell (8b) um — kein VRAM-Swap zu 30b."""
        from src.agents.planner import PlannerAgent
        agent = PlannerAgent()
        agent.model = "qwen3:30b"  # simulate fresh planner

        captured_models = []
        original_call_json = agent.call_json

        def fake_call_json(prompt, system=None):
            captured_models.append(agent.model)
            return {
                "description": "Fixed",
                "root": {"type": "box", "x": 10, "y": 10, "z": 10},
            }

        with patch.object(agent, "call_json", side_effect=fake_call_json):
            agent.run({
                "specification": "Box",
                "validator_feedback": "Hole is not centered",
                "change_description": "",
                "previous_blueprint": {},
                "description": "Box",
            })

        # call_json was invoked with the smaller revise model, not qwen3:30b
        assert len(captured_models) == 1
        from src.config.loader import get_config
        assert captured_models[0] == get_config().models.planner_revise
        # model is restored afterward
        assert agent.model == "qwen3:30b"

    def test_patch_mode_not_used_when_feedback_present(self):
        """Patch-System-Prompt darf nicht aufgerufen werden wenn feedback gesetzt."""
        from src.agents.planner import PlannerAgent, PATCH_SYSTEM_PROMPT
        agent = PlannerAgent()

        captured_systems = []
        def fake_call_json(prompt, system=None):
            captured_systems.append(system)
            return {
                "description": "Fixed",
                "root": {"type": "box", "x": 10, "y": 10, "z": 10},
            }

        with patch.object(agent, "call_json", side_effect=fake_call_json):
            agent.run({
                "specification": "Box",
                "validator_feedback": "Wrong shape",
                "change_description": "make bigger",
                "previous_blueprint": {"description": "Box", "root": {"type": "box"}},
                "description": "Box",
            })

        assert PATCH_SYSTEM_PROMPT not in captured_systems


class TestPlannerPatchMode:
    """Planner nutzt Diff-Strategie wenn change_description gesetzt ist."""

    def test_patch_mode_calls_apply_diff(self):
        from src.agents.planner import PlannerAgent
        agent = PlannerAgent()

        previous_bp = {
            "description": "30mm cube with 8mm hole",
            "root": {"type": "cut",
                     "target": {"type": "box", "x": 30, "y": 30, "z": 30},
                     "tool": {"type": "cylinder", "radius": 4.0, "height": 32.0}}
        }
        diff_response = {
            "changes": [{"path": "root.tool.radius", "new_value": 6.0}],
            "description": "30mm cube with 12mm hole"
        }

        state = {
            "modification": "make hole 12mm",
            "change_description": "Increase cylinder radius from 4mm to 6mm",
            "previous_blueprint": previous_bp,
            "specification": "",
            "validator_feedback": "",
        }

        with patch.object(agent, "call_json", return_value=diff_response):
            with patch.object(agent, "_apply_diff", wraps=agent._apply_diff) as mock_diff:
                agent.run(state)
                mock_diff.assert_called_once()

    def test_patch_mode_uses_patch_system_prompt(self):
        from src.agents.planner import PlannerAgent, PATCH_SYSTEM_PROMPT, SYSTEM_PROMPT
        agent = PlannerAgent()

        state = {
            "modification": "make hole bigger",
            "change_description": "Increase radius from 4mm to 6mm",
            "previous_blueprint": {"description": "cube", "root": {"type": "box"}},
            "specification": "",
            "validator_feedback": "",
        }

        captured_systems = []
        call_count = [0]
        def fake_call_json(prompt, system=None):
            captured_systems.append(system)
            call_count[0] += 1
            if system == PATCH_SYSTEM_PROMPT:
                # First call: return valid diff with an actual change
                return {"changes": [{"path": "root.x", "new_value": 40}], "description": "bigger cube"}
            # Fallback call: return valid Blueprint
            return {"description": "bigger cube", "root": {"type": "box", "x": 40, "y": 30, "z": 30}}

        with patch.object(agent, "call_json", side_effect=fake_call_json):
            agent.run(state)

        assert PATCH_SYSTEM_PROMPT in captured_systems
