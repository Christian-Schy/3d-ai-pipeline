"""
src/agents/plan_validator.py — Validates the CSG-Tree Blueprint before the Coder runs.

Catches geometric logic errors early — before the expensive 30b Coder model processes
a blueprint that's guaranteed to fail or produce wrong output.

Checks:
  - Zero or missing dimensions (depth=0 makes no sense)
  - Slot/cut depth exceeding solid height
  - Union tool z_center formula (must be base_h/2 + tool_h/2)
  - Corner hole positions outside solid bounds
  - Slot length too short (needs solid_dim + slot_width + 2 margin)
  - Feature ordering (holes must precede slots)
  - Corner cut legs within solid bounds

Model: qwen3.5:9b — logic validation, no CadQuery knowledge needed.
"""

import json
import structlog
from pathlib import Path
from src.agents.base import BaseAgent
from src.config.loader import get_config
from src.graph.state import PipelineState

log = structlog.get_logger()

SYSTEM_PROMPT = Path("data/prompts/agents/plan_validator.md").read_text(encoding="utf-8")


class PlanValidatorAgent(BaseAgent):
    """Validates the CSG-Tree Blueprint before the Coder runs.

    Called after Planner, before Coder. On failure, routes back to Planner
    with issue descriptions. Max retries = config.plan_validator.max_retries.
    """

    name = "plan_validator"

    @property
    def model(self) -> str:
        return get_config().models.plan_validator

    def validate(self, state: PipelineState) -> dict:
        """Validate the current blueprint.

        Returns dict with:
          plan_valid: bool
          plan_validation_issues: str  (empty if valid)
          plan_validation_attempts: int  (incremented on failure)
        """
        blueprint = state.get("blueprint", {})
        if not blueprint:
            self.log.warning("plan_validator_no_blueprint")
            return {
                "plan_valid": True,
                "plan_validation_issues": "",
            }

        prompt = (
            f"Validate this CSG-Tree Blueprint:\n"
            f"```json\n{json.dumps(blueprint, indent=2)}\n```\n\n"
            "Check all rules and report any errors."
        )

        try:
            result = self.call_json(prompt, system=SYSTEM_PROMPT)
            is_valid = bool(result.get("is_valid", True))
            issues = result.get("issues", [])
            fixes = result.get("suggested_fixes", [])

            if is_valid:
                self.log.info("plan_validator_ok",
                              blueprint_desc=blueprint.get("description", "")[:60])
                return {
                    "plan_valid": True,
                    "plan_validation_issues": "",
                }
            else:
                # Format issues as a clear text block for the Planner
                issue_lines = ["Plan-Validator found these errors in the blueprint:"]
                for issue in issues:
                    sev = issue.get("severity", "error").upper()
                    desc = issue.get("description", "")
                    itype = issue.get("issue_type", "")
                    issue_lines.append(f"  [{sev}] {itype}: {desc}")
                if fixes:
                    issue_lines.append("\nSuggested fixes:")
                    for fix in fixes:
                        issue_lines.append(f"  - {fix}")

                issues_text = "\n".join(issue_lines)
                current_attempts = state.get("plan_validation_attempts", 0)

                self.log.warning("plan_validator_failed",
                                 issues_count=len(issues),
                                 attempt=current_attempts + 1)
                return {
                    "plan_valid": False,
                    "plan_validation_issues": issues_text,
                    "plan_validation_attempts": current_attempts + 1,
                }

        except (ValueError, ConnectionRefusedError) as e:
            # On error: let the pipeline continue (don't block on validator failure)
            self.log.warning("plan_validator_fallback", error=str(e))
            return {
                "plan_valid": True,
                "plan_validation_issues": "",
            }
