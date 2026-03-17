"""
tests/agents/test_validator_modification.py — Tests für den Validator
im Modifikations-Kontext.

Prüft ob change_description korrekt in den Prompt einfließt.
"""

from unittest.mock import patch


class TestValidatorSemanticWithModification:

    def get_agent(self):
        from src.agents.validator import ValidatorAgent
        return ValidatorAgent()

    def base_state(self):
        return {
            "description": "30mm cube with 8mm hole",
            "change_description": "",
            "blueprint": {"description": "30mm cube with 12mm hole"},
        }

    def test_modification_context_in_prompt(self):
        """Wenn change_description gesetzt ist, steht 'Modification applied' im Prompt."""
        agent = self.get_agent()
        state = {**self.base_state(),
                 "change_description": "Increase cylinder radius from 4mm to 6mm"}

        captured = {}
        def fake_call_json(prompt, system=None):
            captured["prompt"] = prompt
            return {"ok": True, "feedback": ""}

        with patch.object(agent, "call_json", side_effect=fake_call_json):
            agent._check_semantic(
                description="30mm cube with 8mm hole",
                blueprint={"description": "30mm cube with 12mm hole"},
                stats={"watertight": True, "volume_mm3": 23000, "size_mm": [30, 30, 30]},
                state=state,
            )

        assert "Modification applied" in captured["prompt"]
        assert "Increase cylinder radius" in captured["prompt"]

    def test_no_modification_uses_description(self):
        """Ohne change_description wird die normale User-Beschreibung genutzt."""
        agent = self.get_agent()
        state = self.base_state()  # change_description = ""

        captured = {}
        def fake_call_json(prompt, system=None):
            captured["prompt"] = prompt
            return {"ok": True, "feedback": ""}

        with patch.object(agent, "call_json", side_effect=fake_call_json):
            agent._check_semantic(
                description="30mm cube with 8mm hole",
                blueprint={"description": "30mm cube with 8mm hole"},
                stats={"watertight": True, "volume_mm3": 20000, "size_mm": [30, 30, 30]},
                state=state,
            )

        assert "User description" in captured["prompt"]
        assert "Modification applied" not in captured["prompt"]

    def test_modification_not_compared_to_original(self):
        """Validator soll NICHT gegen Originalbeschreibung validieren."""
        agent = self.get_agent()
        state = {**self.base_state(),
                 "change_description": "Increase hole to 12mm"}

        captured = {}
        def fake_call_json(prompt, system=None):
            captured["prompt"] = prompt
            return {"ok": True, "feedback": ""}

        with patch.object(agent, "call_json", side_effect=fake_call_json):
            agent._check_semantic(
                description="30mm cube with 8mm hole",
                blueprint={},
                stats={},
                state=state,
            )

        # Der Hinweis muss explizit da sein
        assert "Do NOT compare against the original" in captured["prompt"]

    def test_fallback_on_llm_error(self):
        """Bei LLM-Fehler optimistisch fallback auf ok=True."""
        agent = self.get_agent()

        with patch.object(agent, "call_json", side_effect=ValueError("bad json")):
            ok, feedback = agent._check_semantic(
                description="cube",
                blueprint={},
                stats={},
                state=self.base_state(),
            )

        assert ok is True  # nie blockieren wegen Connectivity-Problem
