"""Planning nodes: feature_tagger, prompt_assembler, planner, coordinate_validator, plan_validator, function_decomposer."""
from __future__ import annotations
import time
import structlog

from src.graph.state import PipelineState
from src.agents.feature_tagger import FeatureTaggerAgent
from src.agents.function_decomposer import FunctionDecomposerAgent
from src.agents.prompt_assembler import PromptAssembler
from src.agents.plan_validator import PlanValidatorAgent
from src.agents.planner import PlannerAgent
from src.graph.feature_tree import FeatureTree
from ._registry import get_agent
from ._tracing import _make_trace

log = structlog.get_logger()


def feature_tagger_node(state: PipelineState) -> dict:
    """Identify all features and their relationships.

    Runs after Interpreter completes (or after entry_router for modifications).
    Outputs feature_tree (preliminary feature list) + task_classification
    (backward-compat for PromptAssembler).
    """
    _spec = state.get("specification", state.get("description", ""))
    log.info("node_feature_tagger", spec=_spec[:60])
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1
    result = get_agent(FeatureTaggerAgent).tag(state)
    from src.config.loader import get_config as _gc
    _trace = _make_trace(
        agent="feature_tagger", step=_step,
        input_data=_spec,
        output_data=result.get("task_classification", {}),
        start_time=_t0, model=_gc().models.feature_tagger,
    )
    result["agent_traces"] = [_trace]
    return result


def prompt_assembler_node(state: PipelineState) -> dict:
    """Build a focused Planner system prompt from template + rules + RAG.

    Deterministic — no LLM call. Reads task_classification and geometry_state.
    Writes assembled_system_prompt to state — Planner reads this instead of
    its monolithic SYSTEM_PROMPT fallback.

    Also builds per_feature_rules when feature_specs are available (per-feature planning).
    """
    classification = state.get("task_classification", {})
    log.info("node_prompt_assembler",
             template=classification.get("planner_template", "unknown"),
             warnings=classification.get("warnings", []))

    assembler = get_agent(PromptAssembler)
    result = assembler.assemble(state)

    # Per-feature rule loading for per-feature planner mode
    feature_specs = state.get("feature_specs", [])
    if feature_specs:
        pf_result = assembler.assemble_per_feature(state)
        result.update(pf_result)

    return result


def planner_node(state: PipelineState) -> dict:
    """Turn the specification into a structured Blueprint.

    Also reads validator_feedback if we're here due to a semantic failure —
    the Planner uses it to correct the approach.
    """
    feedback = state.get("validator_feedback", "")
    change_desc = state.get("change_description", "")
    coord_issues = state.get("coordinate_validation_issues", "")

    # If coordinate_validator sent us back, inject its issues into plan_validation_issues
    # so the Planner's "plan_fix" mode picks them up.
    if coord_issues and not state.get("plan_validation_issues"):
        state = {**state, "plan_validation_issues": coord_issues}
        log.info("node_planner", mode="coord_fix",
                 issues=coord_issues[:80])
    elif feedback:
        log.info("node_planner", mode="revision", feedback=feedback[:80])
    elif change_desc:
        log.info("node_planner", mode="patch", change=change_desc[:80])
    else:
        log.info("node_planner", mode="fresh",
                 specification=state.get("specification", "")[:60])

    _revision = (bool(feedback)
                 or state.get("plan_validation_attempts", 0) > 0
                 or state.get("coordinate_validation_attempts", 0) > 0)

    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1
    _planner = get_agent(PlannerAgent)

    # Loop-detection: if planner is in revision mode and generated the same blueprint
    # last time, skip calling the LLM again — it would just produce the same result.
    # Mark plan_valid=True to pass validator and let the coder run with what we have.
    _prev_blueprint = state.get("blueprint", {})
    try:
        result = _planner.run(state)
    except ValueError as e:
        # JSON parse failure — LLM produced invalid JSON even after retry.
        # Return empty blueprint so coordinate_validator/plan_validator can route back.
        log.error("node_planner_json_crash", error=str(e)[:200])
        _trace = _make_trace(
            agent="planner", step=_step,
            input_data={"specification": state.get("specification", "")},
            output_data={"error": str(e)[:200]},
            start_time=_t0,
        )
        return {
            "blueprint": _prev_blueprint or {},
            "plan_validation_issues": f"Planner JSON parse error: {str(e)[:150]}. Re-generate the blueprint.",
            "plan_valid": False,
            "agent_traces": [_trace],
        }

    # Clear feedback fields after Planner has read them — prevents re-use on next loop
    result["validator_feedback"] = ""
    result["plan_validation_issues"] = ""
    result["coordinate_validation_issues"] = ""
    result["plan_valid"] = False  # reset so plan_validator runs fresh

    import json as _json
    if feedback and _prev_blueprint and result.get("blueprint"):
        _prev_key = _json.dumps(_prev_blueprint, sort_keys=True)
        _new_key = _json.dumps(result["blueprint"], sort_keys=True)
        if _prev_key == _new_key:
            log.warning("planner_stuck_loop",
                        agent="planner",
                        note="revision produced identical blueprint — skipping to coder")
            result["plan_valid"] = True  # bypass validator, proceed to coder

    from src.config.loader import get_config as _gc
    _raw = getattr(getattr(_planner, "_rag", None), "last_chunks_used", [])
    _rag_chunks = _raw if isinstance(_raw, list) else []
    # When assembled_system_prompt was used, planner skipped enrich_prompt() —
    # RAG was done inside prompt_assembler instead; fall back to those chunks.
    if not _rag_chunks and state.get("assembled_system_prompt", ""):
        _raw2 = getattr(
            getattr(get_agent(PromptAssembler), "_planner_rag", None),
            "last_chunks_used", []
        )
        _rag_chunks = _raw2 if isinstance(_raw2, list) else []
    _fs = state.get("feature_specs", [])
    _trace = _make_trace(
        agent="planner", step=_step,
        input_data={
            "specification": state.get("specification", ""),
            "change_description": change_desc,
            "validator_feedback": feedback,
            "feature_specs_count": len(_fs),
            "per_feature_mode": bool(_fs and len(_fs) >= 2 and any(s.get("parent") for s in _fs)),
        },
        output_data=result.get("blueprint", {}),
        start_time=_t0, model=_gc().models.planner,
        revision=_revision, rag_chunks_used=_rag_chunks,
    )
    result["agent_traces"] = [_trace]
    return result


def function_decomposer_node(state: PipelineState) -> dict:
    """Generate a Python skeleton from the Feature Tree blueprint.

    Rule-based (no LLM). Runs between plan_validator and coder.
    Writes code_skeleton to state — Coder reads it to fill in function bodies.
    If blueprint is not Feature Tree format, writes empty skeleton and Coder
    falls back to legacy CSG-Tree mode.
    """
    blueprint = state.get("blueprint", {})
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1

    if FeatureTree.is_feature_tree(blueprint):
        log.info("node_function_decomposer",
                 build_order=blueprint.get("build_order", []),
                 features=len(blueprint.get("features", {})))
    else:
        log.info("node_function_decomposer_skipped", reason="not_feature_tree")

    result = get_agent(FunctionDecomposerAgent).decompose(state)

    _trace = _make_trace(
        agent="function_decomposer", step=_step,
        input_data={"build_order": blueprint.get("build_order", [])},
        output_data={"skeleton_lines": len(result.get("code_skeleton", "").splitlines())},
        start_time=_t0,
    )
    result["agent_traces"] = [_trace]
    return result


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

    from src.tools.coordinate_validator import run_coordinate_check, format_issues_for_planner
    issues = run_coordinate_check(blueprint)

    errors = [i for i in issues if i.severity == "ERROR"]
    warnings = [i for i in issues if i.severity == "WARNING"]

    _trace = _make_trace(
        agent="coordinate_validator", step=_step,
        input_data={"build_order": blueprint.get("build_order", [])},
        output_data={"errors": len(errors), "warnings": len(warnings)},
        start_time=_t0,
    )

    if errors:
        attempts = state.get("coordinate_validation_attempts", 0) + 1
        log.warning("node_coordinate_validator_failed",
                    errors=len(errors), warnings=len(warnings),
                    attempt=attempts)
        issues_text = format_issues_for_planner(issues)
        return {
            "coordinate_validation_issues": issues_text,
            "coordinate_valid": False,
            "coordinate_validation_attempts": attempts,
            "agent_traces": [_trace],
        }

    if warnings:
        log.info("node_coordinate_validator_warnings", warnings=len(warnings))

    log.info("node_coordinate_validator_ok",
             features=len(blueprint.get("build_order", [])))
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
    result = get_agent(PlanValidatorAgent).validate(state)
    from src.config.loader import get_config as _gc
    _trace = _make_trace(
        agent="plan_validator", step=_step,
        input_data={"blueprint": blueprint},
        output_data={"is_valid": result.get("plan_valid", False),
                     "issues": result.get("plan_validation_issues", "")},
        start_time=_t0, model=_gc().models.plan_validator,
    )
    result["agent_traces"] = [_trace]
    return result
