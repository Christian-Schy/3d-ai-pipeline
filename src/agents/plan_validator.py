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
import re
import structlog
from src.agents.base import BaseAgent
from src.config.loader import get_config
from src.graph.state import PipelineState
from src.utils.prompt_loader import load_prompt
from src.rag.plan_validator_rag import PlanValidatorRAG

log = structlog.get_logger()

_prompt = load_prompt("prompt_plan_validator.py")
SYSTEM_PROMPT = _prompt.SYSTEM_PROMPT


class PlanValidatorAgent(BaseAgent):
    """Validates the CSG-Tree Blueprint before the Coder runs.

    Called after Planner, before Coder. On failure, routes back to Planner
    with issue descriptions. Max retries = config.plan_validator.max_retries.
    """

    name = "plan_validator"

    @property
    def model(self) -> str:
        return get_config().models.plan_validator

    def __init__(self):
        super().__init__()
        self._rag = PlanValidatorRAG()
        self._rag_ready = False

    def _ensure_rag(self):
        if not self._rag_ready:
            try:
                self._rag.build()
            except FileNotFoundError:
                self.log.warning("plan_validator_rag_missing",
                                 path="data/knowledge/rag_agents/22_plan_validation")
            self._rag_ready = True

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

        feature_types = " ".join(
            f.get("type", "") for f in blueprint.get("features", {}).values()
            if isinstance(f, dict)
        ) or blueprint.get("description", "blueprint validation")

        # Truncate top-level notes to avoid token bloat (LLM sometimes writes essays here)
        blueprint_trimmed = dict(blueprint)
        if isinstance(blueprint_trimmed.get("notes"), str):
            blueprint_trimmed["notes"] = blueprint_trimmed["notes"][:150]

        prompt = (
            f"Validate this Blueprint:\n"
            f"```json\n{json.dumps(blueprint_trimmed, indent=2)}\n```\n\n"
            "Check all rules and report any errors."
        )

        self._ensure_rag()
        prompt = self._rag.enrich_prompt(prompt, feature_types)

        try:
            result = self.call_json(prompt, system=SYSTEM_PROMPT)
            # New prompt uses "valid"/"errors"; legacy used "is_valid"/"issues"
            is_valid = bool(result.get("valid", result.get("is_valid", True)))
            errors = result.get("errors", result.get("issues", []))
            summary = result.get("summary", "")

            # Deterministic post-filter: drop Check-6 false positives for
            # holes that intentionally pierce the pocket floor. The LLM
            # cannot reliably honor the prompt exception, so we strip these
            # errors after the call. If nothing critical remains, we flip
            # the verdict back to valid.
            errors = _drop_pocket_floor_depth_errors(errors, blueprint)
            if not is_valid and not _has_blocking_errors(errors):
                is_valid = True

            if is_valid:
                self.log.info("plan_validator_ok",
                              blueprint_desc=blueprint.get("description", "")[:60],
                              summary=summary[:60])
                return {
                    "plan_valid": True,
                    "plan_validation_issues": "",
                }
            else:
                # Format errors as a clear text block for the Planner
                error_lines = ["Plan-Validator found these errors in the blueprint:"]
                for err in errors:
                    sev = err.get("severity", "ERROR").upper()
                    msg = err.get("message", err.get("description", ""))
                    check = err.get("check", err.get("issue_type", ""))
                    check_str = f"[Check {check}] " if check else ""
                    error_lines.append(f"  [{sev}] {check_str}{msg}")
                if summary:
                    error_lines.append(f"\nSummary: {summary}")

                issues_text = "\n".join(error_lines)
                current_attempts = state.get("plan_validation_attempts", 0)

                self.log.warning("plan_validator_failed",
                                 errors_count=len(errors),
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


# ── Deterministic error filters ────────────────────────────────────────────

# Matches the LLM's typical Check-6 phrasing:
#   "Feature 'foo' (depth 20) is larger than parent 'bar' (depth 10)"
#   "Feature \"foo\" depth=20 exceeds parent ..."
_DEPTH_VS_PARENT_PATTERN = re.compile(
    r"feature[\s'\"]+(?P<fid>[\w\-]+)[\s'\"]*"
    r".*?(?:larger\s+than|exceeds?)\s+parent",
    re.IGNORECASE,
)


def _drop_pocket_floor_depth_errors(errors: list, blueprint: dict) -> list:
    """Filter out Check-6 errors for holes that intentionally pierce the
    pocket floor (depth_reference_applied="pocket_floor").

    The LLM-validator's depth-vs-parent rule treats `depth = depth_local +
    parent_depth` as oversized, but that is the resolver's intended output
    for in-pocket holes — the bohrung goes through the pocket floor into
    the parent material. We strip these errors deterministically.
    """
    if not isinstance(errors, list):
        return errors

    features = (blueprint.get("features") or {}) if isinstance(blueprint, dict) else {}
    if not isinstance(features, dict):
        features = {}

    kept = []
    for err in errors:
        if not isinstance(err, dict):
            kept.append(err)
            continue
        check = err.get("check", err.get("issue_type"))
        msg = (err.get("message") or err.get("description") or "")

        # Only consider Check 6 (or unnumbered errors with the same wording).
        if check not in (6, "6", None) and not isinstance(check, str):
            kept.append(err)
            continue
        m = _DEPTH_VS_PARENT_PATTERN.search(msg)
        if not m:
            kept.append(err)
            continue

        fid = m.group("fid")
        feat = features.get(fid)
        if not isinstance(feat, dict):
            kept.append(err)
            continue
        params = feat.get("params") or {}
        if (params.get("depth_reference_applied") or "").lower() == "pocket_floor":
            log.info("plan_validator_filter_pocket_floor",
                     feature=fid, dropped_message=msg[:80])
            continue
        kept.append(err)

    return kept


def _has_blocking_errors(errors: list) -> bool:
    """Return True iff the list still contains at least one ERROR-severity
    entry. WARNINGs do not block the pipeline."""
    if not isinstance(errors, list):
        return bool(errors)
    for err in errors:
        if not isinstance(err, dict):
            return True
        sev = (err.get("severity") or "ERROR").upper()
        if sev == "ERROR":
            return True
    return False
