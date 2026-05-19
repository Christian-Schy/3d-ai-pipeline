"""Planning node subset split out from planning_nodes.py."""
from __future__ import annotations

import time

import structlog

from src.agents.plan_validator import PlanValidatorAgent
from src.graph.feature_tree import FeatureTree
from src.graph.state import PipelineState

from . import _registry
from ._tracing import _make_trace

log = structlog.get_logger()

def coordinate_validator_node(state: PipelineState) -> dict:
    """Rule-based coordinate and dimension check after the Planner.

    Runs deterministically — no LLM needed. Checks that feature dimensions
    are physically plausible (fits in parent, depth ≤ material, bolt circle
    geometry, wall thickness). Skips CSG-Tree blueprints.

    Returns coordinate_validation_issues (str). Empty = all passed.
    On ERROR-severity issues: routes back to Planner. WARNINGs pass through.
    """
    blueprint = state.get("blueprint", {})
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1

    if not blueprint:
        return {"coordinate_validation_issues": "", "coordinate_valid": True}

    from src.tools.coordinate_validator import format_issues_for_planner, run_coordinate_check
    issues = run_coordinate_check(blueprint)

    errors = [i for i in issues if i.severity == "ERROR"]
    warnings = [i for i in issues if i.severity == "WARNING"]

    # Bug 3 (e3ddd2d0): the trace previously only carried counts. When the
    # retry loop hit max_retries, the actual issue texts vanished and the
    # run reported success=True with silently-unresolved geometry errors.
    # Persist the formatted issue list (capped) so post-mortem analysis
    # can see WHAT failed without re-running anything.
    issue_lines = [
        f"[{i.severity}] {i.feature_id} — {i.check}: {i.message}"
        for i in issues
    ]

    _output: dict = {
        "errors": len(errors),
        "warnings": len(warnings),
        "issues": issue_lines[:50],  # cap for trace size
    }

    if errors:
        from src.config.loader import get_config as _gc_cv
        attempts = state.get("coordinate_validation_attempts", 0) + 1
        max_retries = _gc_cv().plan_validator.max_retries
        will_be_swallowed = attempts >= max_retries
        _output["attempts"] = attempts
        _output["max_retries"] = max_retries
        _output["unresolved_at_max_retries"] = will_be_swallowed

        log.warning("node_coordinate_validator_failed",
                    errors=len(errors), warnings=len(warnings),
                    attempt=attempts, max_retries=max_retries,
                    swallowed=will_be_swallowed)
        if will_be_swallowed:
            log.error("node_coordinate_validator_swallowed",
                      errors=len(errors), issues=issue_lines[:5])
        issues_text = format_issues_for_planner(issues)
        _trace = _make_trace(
            agent="coordinate_validator", step=_step,
            input_data={"build_order": blueprint.get("build_order", [])},
            output_data=_output,
            start_time=_t0,
        )
        return {
            "coordinate_validation_issues": issues_text,
            "coordinate_valid": False,
            "coordinate_validation_attempts": attempts,
            # Sticky flag the executor / final state can read to mark a run
            # as "succeeded structurally but with unresolved coord errors".
            "coordinate_errors_unresolved": will_be_swallowed,
            "agent_traces": [_trace],
        }

    if warnings:
        log.info("node_coordinate_validator_warnings", warnings=len(warnings))

    log.info("node_coordinate_validator_ok",
             features=len(blueprint.get("build_order", [])))
    _trace = _make_trace(
        agent="coordinate_validator", step=_step,
        input_data={"build_order": blueprint.get("build_order", [])},
        output_data=_output,
        start_time=_t0,
    )
    return {
        "coordinate_validation_issues": "",
        "coordinate_valid": True,
        "agent_traces": [_trace],
    }


def plan_validator_node(state: PipelineState) -> dict:
    """Validate the Blueprint before the expensive Coder runs.

    First runs a fast deterministic quick_check (feature count + depth consistency).
    If that passes, runs the LLM Plan-Validator for geometric logic errors.
    On failure, routes back to Planner (max config.plan_validator.max_retries).

    In Häppchen mode (specialized agents produced the blueprint), the LLM validator
    is skipped — the specialized agents already validated structure and positions.
    Only the deterministic quick_check runs (for Feature Tree: skipped entirely).
    """
    blueprint = state.get("blueprint", {})
    spec = state.get("specification") or state.get("description", "")
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1

    # Fast deterministic check: does blueprint contain all features from spec?
    # Runs always — even on patches, to catch missing features or wrong depth values.
    # Skip for Feature Tree blueprints: quick_check is CSG-Tree specific.
    if blueprint and spec and not FeatureTree.is_feature_tree(blueprint):
        try:
            from src.tools.geometry_precheck import quick_check
            quick_issues = quick_check(blueprint, spec)
            if quick_issues:
                issues_text = " | ".join(i["message"] for i in quick_issues)
                attempts = state.get("plan_validation_attempts", 0) + 1
                log.warning("node_plan_validator_quick_fail",
                            issues=issues_text[:120], attempt=attempts)
                _trace = _make_trace(
                    agent="plan_validator", step=_step,
                    input_data={"blueprint": blueprint},
                    output_data={"is_valid": False, "issues": issues_text, "source": "quick_check"},
                    start_time=_t0,
                )
                return {
                    "plan_valid": False,
                    "plan_validation_issues": f"Blueprint is missing features or has wrong depth values: {issues_text}",
                    "plan_validation_attempts": attempts,
                    "agent_traces": [_trace],
                }
        except Exception as _qc_err:
            log.warning("node_plan_validator_quick_check_failed", error=str(_qc_err))

    # Skip LLM plan_validator for non-additive patch modifications.
    # A pure value/position change on a previously-validated blueprint cannot introduce
    # structural errors — the quick_check above is sufficient.
    # LLM still runs for: fresh blueprints, additive changes, revisions after validator feedback.
    change_desc = state.get("change_description", "")
    is_additive = state.get("is_additive", False)
    validator_feedback = state.get("validator_feedback", "")
    if (change_desc
            and not is_additive
            and not validator_feedback
            and state.get("plan_validation_attempts", 0) == 0):
        log.info("node_plan_validator_skipped",
                 reason="non_additive_patch", change=change_desc[:60])
        _trace = _make_trace(
            agent="plan_validator", step=_step,
            input_data={"blueprint": blueprint},
            output_data={"is_valid": True, "source": "skipped_non_additive_patch"},
            start_time=_t0,
        )
        return {"plan_valid": True, "agent_traces": [_trace]}

    log.info("node_plan_validator",
             blueprint_desc=blueprint.get("description", "")[:60],
             attempt=state.get("plan_validation_attempts", 0))
    result = _registry.get_agent(PlanValidatorAgent).validate(state)
    from src.config.loader import get_config as _gc
    _trace = _make_trace(
        agent="plan_validator", step=_step,
        input_data={"blueprint": blueprint},
        output_data={"is_valid": result.get("plan_valid", False),
                     "issues": result.get("plan_validation_issues", "")},
        start_time=_t0, model=_gc().models.plan_validator,
        raw_response=_registry.get_raw_response(PlanValidatorAgent),
    )
    result["agent_traces"] = [_trace]
    return result


