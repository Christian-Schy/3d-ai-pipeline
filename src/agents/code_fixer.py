"""
src/agents/code_fixer.py — Phase 2 specialist: analyzes repeated code failures.

The CodeFixer is called when the Coder has failed 2+ times.
At that point, the error is probably not a simple typo — there's a
pattern to the failure that needs diagnosis.

What CodeFixer does:
  - Reads all previous error messages and failed code attempts
  - Identifies the root cause (wrong API usage, wrong geometry approach, etc.)
  - Writes a concrete fix_plan string
  - Coder reads fix_plan on its next attempt as additional guidance

Why not just give Coder more attempts?
  After 2 failures with the same approach, more attempts of the same thing
  won't help. CodeFixer forces a step back: diagnose first, then fix.

Model: qwen3:8b — diagnosis doesn't need the big model, Coder does the heavy lifting.
"""

import json
import structlog
from pathlib import Path
from src.agents.base import BaseAgent
from src.graph.state import PipelineState

log = structlog.get_logger()

SYSTEM_PROMPT = Path("data/prompts/agents/code_fixer.md").read_text(encoding="utf-8")


class CodeFixerAgent(BaseAgent):
    """Diagnoses repeated code failures and produces a fix plan for the Coder.

    Called by code_fixer_node in Phase 2 of the error loop.
    Returns {"fix_plan": str} — written to state, read by coder_node.
    """

    name = "code_fixer"

    @property
    def model(self) -> str:
        from src.config.loader import get_config
        return get_config().models.code_fixer

    def diagnose(self, state: PipelineState) -> dict:
        """Analyze the failure pattern and return a fix plan.

        Returns: {"fix_plan": "..."}
        """
        error = state.get("execution_error") or state.get("validation_error", "")
        code = state.get("code", "")
        blueprint = state.get("blueprint", {})
        attempts = state.get("attempts", 0)

        self.log.info("code_fixer_start", attempts=attempts, error=error[:80])

        prompt = (
            f"## Failed after {attempts} attempts\n\n"
            f"## Blueprint\n```json\n{json.dumps(blueprint, indent=2)}\n```\n\n"
            f"## Last code that failed\n```python\n{code[:2000]}\n```\n\n"
            f"## Error message\n{error}\n\n"
            "Diagnose the root cause and write a fix plan."
        )

        # Fast-path: known error patterns don't need LLM diagnosis
        fast_fix = self._fast_fix(error, code)
        if fast_fix:
            self.log.info("code_fixer_fast_fix", pattern=fast_fix[:60])
            return {"fix_plan": fast_fix}

        try:
            raw = self.call(prompt, system=SYSTEM_PROMPT)
        except (ConnectionRefusedError, ValueError) as e:
            self.log.warning("code_fixer_fallback", error=str(e))
            return {"fix_plan": "Could not reach LLM. Try reducing complexity or check the error message manually."}

        # Parse plain-text format: ROOT_CAUSE: ... / FIX_PLAN: ...
        root_cause, fix_plan = "", ""
        for line in raw.splitlines():
            if line.startswith("ROOT_CAUSE:"):
                root_cause = line[len("ROOT_CAUSE:"):].strip()
            elif line.startswith("FIX_PLAN:"):
                fix_plan = line[len("FIX_PLAN:"):].strip()
            elif fix_plan:
                fix_plan += "\n" + line  # continuation lines

        if not fix_plan:
            fix_plan = raw.strip()  # fallback: use whole response

        self.log.info("code_fixer_done",
                      root_cause=root_cause[:80],
                      fix_plan_len=len(fix_plan))

        combined = f"Root cause: {root_cause}\n\nFix plan:\n{fix_plan}" if root_cause else fix_plan
        return {"fix_plan": combined}

    @staticmethod
    def _fast_fix(error: str, code: str) -> str:
        """Return an instant fix plan for known error patterns — no LLM needed."""
        if "fillet" in error.lower() and "fillet" in code:
            return (
                "Root cause: fillet() fails after hole() — CadQuery cannot fillet "
                "edges adjacent to through-holes with this selector.\n\n"
                "Fix plan:\n"
                "1. Remove ALL .fillet() calls from the code completely.\n"
                "2. Do NOT replace fillet with chamfer — omit edge treatment entirely.\n"
                "3. Keep the rest of the code unchanged."
            )
        return ""
