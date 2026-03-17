"""
src/agents/task_classifier.py — Classifies the modeling task to select template + rules.

Sits between Interpreter and Planner. Outputs:
  - task_type:     which kind of modeling operation is requested
  - difficulty:    low / medium / high
  - rag_categories: which knowledge categories are relevant
  - planner_template: which focused template the PromptAssembler should use
  - warnings:      known pitfalls detected in the spec

Model: qwen3.5:9b — classification only, no geometry knowledge needed.
"""

import structlog
from pathlib import Path
from src.agents.base import BaseAgent
from src.config.loader import get_config
from src.graph.state import PipelineState

log = structlog.get_logger()

SYSTEM_PROMPT = Path("data/prompts/agents/task_classifier.md").read_text(encoding="utf-8")


class TaskClassifierAgent(BaseAgent):
    """Classifies the modeling task to guide template and rule selection.

    Called after Interpreter completes. Output is stored in task_classification
    and consumed by PromptAssembler to build a focused Planner prompt.
    """

    name = "task_classifier"

    @property
    def model(self) -> str:
        return get_config().models.task_classifier

    def classify(self, state: PipelineState) -> dict:
        """Classify the modeling task.

        Returns:
            dict with task_type, difficulty, requires_current_geometry,
            rag_categories, planner_template, warnings
        """
        specification = state.get("specification") or state.get("description", "")
        change_desc = state.get("change_description", "")

        # For modifications, classify the change, not the original spec
        text_to_classify = change_desc if change_desc else specification

        # Include previous blueprint context for better modification classification
        previous_bp = state.get("previous_blueprint", {})
        context = ""
        if previous_bp and change_desc:
            import json
            context = (
                f"\nExisting model summary: {previous_bp.get('description', '')}\n"
                f"Root type: {previous_bp.get('root', {}).get('type', 'unknown')}\n"
                f"Features count: {len(previous_bp.get('features', []))}\n"
            )

        prompt = f"Specification to classify:\n{text_to_classify}{context}"

        try:
            result = self.call_json(prompt, system=SYSTEM_PROMPT)

            # Validate required fields with sensible defaults
            task_type = result.get("task_type", "complex_multi_step")
            difficulty = result.get("difficulty", "medium")
            requires_geo = bool(result.get("requires_current_geometry", False))
            rag_cats = result.get("rag_categories", [])
            template = result.get("planner_template", "template_complex")
            warnings = result.get("warnings", [])

            self.log.info("task_classifier_done",
                          task_type=task_type,
                          difficulty=difficulty,
                          template=template,
                          warnings=warnings)

            return {
                "task_classification": {
                    "task_type": task_type,
                    "difficulty": difficulty,
                    "requires_current_geometry": requires_geo,
                    "rag_categories": rag_cats,
                    "planner_template": template,
                    "warnings": warnings,
                }
            }

        except (ValueError, ConnectionRefusedError) as e:
            self.log.warning("task_classifier_fallback", error=str(e))
            # Safe fallback: use complex template (contains everything)
            return {
                "task_classification": {
                    "task_type": "complex_multi_step",
                    "difficulty": "high",
                    "requires_current_geometry": False,
                    "rag_categories": ["holes_single", "slots_grooves", "boolean_ops"],
                    "planner_template": "template_complex",
                    "warnings": [],
                }
            }
