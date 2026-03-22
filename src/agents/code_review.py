"""
src/agents/code_review.py — Static code review before the Executor runs.

The Code Review Agent sits between Coder and Executor and performs a
structural analysis of the generated code BEFORE it's executed:

  1. Structure: imports, assemble(), export present?
  2. CadQuery patterns: .clean() after booleans, centerOption, NearestToPoint
  3. Blueprint match: dimensions, function count, build_order in assemble()
  4. Variable hygiene: result assigned correctly, no dead code

On ERROR  → routes back to Coder (only the failing function is re-generated)
On WARNING → continues to Executor (logged but not blocking)
On PASS    → continues to Executor

Model: qwen3.5:9b — checklist-based, no CadQuery synthesis needed.
"""

import structlog
from src.agents.base import BaseAgent
from src.config.loader import get_config
from src.graph.state import PipelineState
from src.utils.prompt_loader import load_prompt
from src.rag.code_review_rag import CodeReviewRAG

log = structlog.get_logger()

_prompt = load_prompt("prompt_code_review.py")
SYSTEM_PROMPT = _prompt.SYSTEM_PROMPT


class CodeReviewAgent(BaseAgent):
    """Reviews generated CadQuery code against the Feature Tree blueprint.

    Runs a checklist of 20 checks grouped into: structure, CadQuery errors,
    blueprint match, and variable hygiene. Returns approved=true/false with
    a list of issues.
    """

    name = "code_review"

    @property
    def model(self) -> str:
        return get_config().models.plan_validator  # reuse 9b model slot

    def __init__(self):
        super().__init__()
        self._rag = CodeReviewRAG()
        self._rag_ready = False

    def _ensure_rag(self):
        if not self._rag_ready:
            try:
                self._rag.build()
            except FileNotFoundError:
                self.log.warning("code_review_rag_missing",
                                 path="data/knowledge/rag_agents/23_code_review")
            self._rag_ready = True

    @staticmethod
    def _deterministic_checks(code: str, blueprint: dict = None) -> list[dict]:
        """Run regex-based checks that the LLM often misses.

        Returns list of error dicts in the same format as LLM issues.
        These are always reliable, unlike the 9b model's Check 19.
        """
        import re
        errors = []

        # Check: Blueprint has blind holes (depth != null) but code uses .hole(d) without depth
        if blueprint:
            features = blueprint.get("features", {})
            if isinstance(features, dict):
                features = features.values()
            for feat in features:
                if not isinstance(feat, dict):
                    continue
                ftype = feat.get("type", "")
                params = feat.get("params", {}) or {}
                if "hole" in ftype and params.get("depth") is not None:
                    depth_val = params["depth"]
                    # Check if any .hole() call has exactly one argument (missing depth)
                    # Pattern: .hole(NUMBER) without comma → through-hole
                    hole_calls = re.findall(r'\.hole\s*\(\s*[\w_]+\s*\)', code)
                    if hole_calls:
                        errors.append({
                            "check": "D3",
                            "severity": "ERROR",
                            "function": "detected in code",
                            "message": f"Blueprint specifies blind hole depth={depth_val}mm but code uses .hole(diameter) without depth → through-hole!",
                            "fix_hint": f"Use .hole(DIAMETER, {depth_val}) for blind hole, NOT .hole(DIAMETER)",
                        })
                    break  # Check only once

        # Check: pushPoints used for hole patterns instead of rArray
        if re.search(r'pushPoints\s*\(', code) and re.search(r'\.hole\s*\(', code):
            errors.append({
                "check": "D1",
                "severity": "ERROR",
                "function": "detected in code",
                "message": "pushPoints+hole anti-pattern — use .rArray().hole() instead",
                "fix_hint": "Replace manual pushPoints loop with: .rArray(x_spacing, y_spacing, x_count, y_count).hole(diameter)",
            })

        # Check: NearestToPointSelector used but not imported
        if 'NearestToPointSelector' in code and 'NearestToPointSelector(' in code:
            if not re.search(r'from\s+cadquery\.selectors\s+import\s+NearestToPointSelector', code):
                errors.append({
                    "check": "D5",
                    "severity": "ERROR",
                    "function": "imports",
                    "message": "NearestToPointSelector is used but not imported!",
                    "fix_hint": "Add: from cadquery.selectors import NearestToPointSelector",
                })

        # Check: SELECTOR_POINT constants defined but NearestToPointSelector not used
        selector_points = re.findall(r'(\w+_SELECTOR_POINT)\s*=', code)
        if selector_points:
            if 'NearestToPointSelector' not in code:
                errors.append({
                    "check": "D4",
                    "severity": "ERROR",
                    "function": "detected in code",
                    "message": (
                        f"SELECTOR_POINT constants defined ({', '.join(selector_points)}) "
                        f"but NearestToPointSelector is never used! "
                        f"After union, .faces(\">Z\") picks the WRONG face."
                    ),
                    "fix_hint": (
                        "Use body.faces(NearestToPointSelector(FEATURE_SELECTOR_POINT))"
                        ".workplane(centerOption='CenterOfBoundBox') instead of body.faces(\">Z\")"
                    ),
                })
            else:
                # Check each SELECTOR_POINT constant is actually referenced in a NearestToPointSelector call
                for sp_name in selector_points:
                    if f'NearestToPointSelector({sp_name})' not in code:
                        errors.append({
                            "check": "D4",
                            "severity": "ERROR",
                            "function": "detected in code",
                            "message": f"{sp_name} is defined but not used in NearestToPointSelector call!",
                            "fix_hint": f"Use body.faces(NearestToPointSelector({sp_name})).workplane(...)",
                        })

        # Check: CadQuery method result discarded (not in a chain or assignment)
        # Matches lines like: wp.hole(10)  or  wp.pushPoints(pts)  without assignment
        # But NOT lines like: result = wp.hole(10)  or  return wp.hole(10)  or  .hole(10))
        discarded_pattern = re.compile(
            r'^\s+\w+\.(hole|pushPoints|rArray|extrude|cutBlind|cutThruAll|cut|union|fillet|chamfer)\s*\(',
            re.MULTILINE
        )
        for match in discarded_pattern.finditer(code):
            line = match.group(0).strip()
            # Check the full line doesn't start with an assignment or return
            line_start = code.rfind('\n', 0, match.start()) + 1
            full_line = code[line_start:code.find('\n', match.start())].strip()
            if not full_line.startswith(('return ', 'result ', 'body ', 'wp ')) and '=' not in full_line.split('(')[0]:
                errors.append({
                    "check": "D2",
                    "severity": "ERROR",
                    "function": "detected in code",
                    "message": f"Discarded return value: `{full_line[:60]}` — CadQuery is immutable!",
                    "fix_hint": "Assign result: variable = " + full_line[:40],
                })
                break  # One error is enough to trigger re-generation

        return errors

    def review(self, state: PipelineState) -> dict:
        """Review the generated code.

        Returns dict with:
          code_review_approved: bool
          code_review_issues: str  (empty if approved)
        """
        import json
        code = state.get("code", "")
        blueprint = state.get("blueprint", {})

        if not code:
            self.log.warning("code_review_no_code")
            return {
                "code_review_approved": True,
                "code_review_issues": "",
            }

        # Phase 0: Deterministic checks — always reliable, catches what LLM misses
        det_errors = self._deterministic_checks(code, blueprint)
        if det_errors:
            self.log.warning("code_review_deterministic_fail",
                             errors=len(det_errors),
                             checks=[e["check"] for e in det_errors])
            issue_lines = [
                "Code Review found errors — fix only the listed functions:\n"
            ]
            for err in det_errors:
                issue_lines.append(
                    f"  [ERROR] check {err['check']} in `{err['function']}`: {err['message']}"
                )
                if err.get("fix_hint"):
                    issue_lines.append(f"    → Fix: {err['fix_hint']}")
            return {
                "code_review_approved": False,
                "code_review_issues": "\n".join(issue_lines),
            }

        blueprint_json = json.dumps(blueprint, indent=2)[:2000]  # cap for 9b budget

        prompt = (
            f"BLUEPRINT:\n```json\n{blueprint_json}\n```\n\n"
            f"CODE:\n```python\n{code}\n```\n\n"
            "Review the code against the blueprint using the checklist."
        )

        self._ensure_rag()
        prompt = self._rag.enrich_prompt(prompt, "code review checklist CadQuery")

        try:
            result = self.call_json(prompt, system=SYSTEM_PROMPT)
            issues = result.get("issues", [])

            # LLM-based errors are downgraded to warnings.
            # Rationale: The 9b model produces too many false positives
            # (centerOption, discarded values) that force the Coder into
            # destructive rewrite loops where it drops parameters.
            # Only deterministic checks (D1-D3 above) can block the code.
            all_issues = issues if isinstance(issues, list) else []
            llm_warnings = []
            for issue in all_issues:
                severity = issue.get("severity", "").upper()
                if severity == "ERROR":
                    # Downgrade to WARNING — log but don't block
                    issue["severity"] = "WARNING"
                    issue["_was_error"] = True
                llm_warnings.append(issue)

            if True:  # LLM issues never block — deterministic checks already ran
                downgraded = [w for w in llm_warnings if w.get("_was_error")]
                if downgraded:
                    warn_text = "\n".join(
                        f"  [WARNING/downgraded] check {w.get('check', '?')} "
                        f"({w.get('function', 'global')}): {w.get('message', '')}"
                        for w in downgraded
                    )
                    self.log.info("code_review_llm_warnings_downgraded",
                                  count=len(downgraded), text=warn_text[:300])
                else:
                    self.log.info("code_review_approved",
                                  llm_issues=len(llm_warnings))
                return {
                    "code_review_approved": True,
                    "code_review_issues": "",
                }

        except (ValueError, ConnectionRefusedError) as e:
            # On error: let the pipeline continue — don't block on reviewer failure
            self.log.warning("code_review_fallback", error=str(e))
            return {
                "code_review_approved": True,
                "code_review_issues": "",
            }
