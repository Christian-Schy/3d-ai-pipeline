"""
src/agents/modification_interpreter.py — Understands modification requests.

When a user types something after a successful run, two cases are possible:

  1. New request:    "A cylinder 20mm diameter"
     → Start fresh, ignore previous blueprint

  2. Modification:   "Make the hole bigger" / "Add a chamfer" / "Increase height to 40mm"
     → Parse what changed, keep rest of blueprint

This agent decides which case it is and — if it's a modification —
produces a clear change description the Planner can apply to the
existing Blueprint.

Model: qwen3:8b — classification + extraction, no big model needed.
"""

import structlog
from src.agents.base import BaseAgent
from src.graph.state import PipelineState
from src.utils.prompt_loader import load_prompt

log = structlog.get_logger()

_prompt = load_prompt("prompt_modification_interpreter.py")
SYSTEM_PROMPT = _prompt.SYSTEM_PROMPT


class ModificationInterpreterAgent(BaseAgent):
    """Classifies user input as modification or new request.

    Called by the entry router before the graph starts.
    Returns {"is_modification": bool, "change_description": str}
    """

    name = "modification_interpreter"

    @property
    def model(self) -> str:
        from src.config.loader import get_config
        return get_config().models.modification_interpreter

    def classify(self, state: PipelineState) -> dict:
        """Decide if the input is a modification or new request.

        Returns:
          is_modification: bool
          change_description: str — precise change for the Planner (if modification)
        """
        user_input = state.get("modification") or state.get("description", "")
        previous_blueprint = state.get("previous_blueprint", {})

        # No previous blueprint = can't be a modification
        if not previous_blueprint:
            self.log.info("modification_classifier", result="new_request",
                          reason="no_previous_blueprint")
            return {"is_modification": False, "is_additive": False,
                    "change_description": "", "changed_features": []}

        import json
        prompt = (
            f"Previous model blueprint:\n"
            f"```json\n{json.dumps(previous_blueprint, indent=2)[:1000]}\n```\n\n"
            f"User input: {user_input}\n\n"
            "Is this a modification to the existing model, or a new request?"
        )

        try:
            result = self.call_json(prompt, system=SYSTEM_PROMPT)
            is_mod = bool(result.get("is_modification", False))
            is_additive = bool(result.get("is_additive", False))
            change_desc = (result.get("change_description") or "").strip()

            changed_features = result.get("changed_features", [])
            if not isinstance(changed_features, list):
                changed_features = []
            # Only propagate changed_features for actual modifications
            if not is_mod:
                changed_features = []

            self.log.info("modification_classifier",
                          result="modification" if is_mod else "new_request",
                          is_additive=is_additive,
                          change=change_desc[:80],
                          changed_features=changed_features)
            # UI chat: show what the modification interpreter understood
            if is_mod:
                self.log.info("modification_interpreter_done",
                              change=change_desc[:300],
                              is_additive=is_additive,
                              changed_features=changed_features)
            return {
                "is_modification": is_mod,
                "is_additive": is_additive,
                "change_description": change_desc,
                "changed_features": changed_features,
            }

        except (ValueError, ConnectionRefusedError) as e:
            # Fallback: treat as new request to be safe
            self.log.warning("modification_classifier_fallback", error=str(e))
            return {
                "is_modification": False,
                "is_additive": False,
                "change_description": "",
                "changed_features": [],
            }
