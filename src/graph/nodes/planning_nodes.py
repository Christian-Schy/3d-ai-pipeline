"""Planning nodes: feature_tagger, feature_assigner, feature_position_assigner, part_position_assigner, blueprint_assembler, prompt_assembler, planner, coordinate_validator, plan_validator, function_decomposer."""
from __future__ import annotations
import time
import structlog

from src.graph.state import PipelineState
from src.agents.feature_tagger import FeatureTaggerAgent
from src.agents.feature_assigner import FeatureAssignerAgent
from src.agents.feature_position_assigner import FeaturePositionAssignerAgent
from src.agents.part_position_assigner import PartPositionAssignerAgent
from src.agents.blueprint_assembler import BlueprintAssembler
from src.agents.function_decomposer import FunctionDecomposerAgent
from src.agents.prompt_assembler import PromptAssembler
from src.agents.plan_validator import PlanValidatorAgent
from src.agents.planner import PlannerAgent
from src.graph.feature_tree import FeatureTree
from ._registry import get_agent, get_raw_response
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
        raw_response=get_raw_response(FeatureTaggerAgent),
    )
    result["agent_traces"] = [_trace]
    return result


def feature_assigner_node(state: PipelineState) -> dict:
    """Assign parent, operation, and dimensions to each feature.

    Part of the Häppchen pipeline: Feature Tagger → **Feature Assigner** →
    Position Assigner → Blueprint Assembler → Planner (review).
    """
    _spec = state.get("specification", state.get("description", ""))
    log.info("node_feature_assigner", spec=_spec[:60])
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1
    result = get_agent(FeatureAssignerAgent).assign(state)

    fa = result.get("feature_assignments", {})
    # Log full assignments for debugging (parent, operation, params per feature)
    _fa_summary = {
        fid: {"parent": d.get("parent"), "op": d.get("operation"), "params": d.get("params", {})}
        for fid, d in fa.items() if isinstance(d, dict)
    }
    from src.config.loader import get_config as _gc
    _trace = _make_trace(
        agent="feature_assigner", step=_step,
        input_data={"features": list(state.get("feature_tree", {}).get("features_identified", []))},
        output_data={"assignments": len(fa), "details": _fa_summary},
        start_time=_t0, model=_gc().models.feature_assigner,
        raw_response=get_raw_response(FeatureAssignerAgent),
    )
    result["agent_traces"] = [_trace]
    return result


def feature_position_assigner_node(state: PipelineState) -> dict:
    """Assign face, alignment, and orientation hints to subtract/modify features.

    Part of the Häppchen pipeline: Feature Tagger → Feature Assigner →
    **Feature Position Assigner** → Part Position Assigner → Blueprint Assembler.
    Only handles holes, slots, pockets, fillets, chamfers etc.
    Skipped by Agent Dispatcher if no subtract/modify features detected.
    """
    active = state.get("active_agents", [])
    if active and "feature_position_assigner" not in active:
        log.info("node_feature_position_assigner_skipped", reason="not_in_active_agents")
        return {"feature_position_assignments": {}}

    _spec = state.get("specification", state.get("description", ""))
    log.info("node_feature_position_assigner", spec=_spec[:60])
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1
    result = get_agent(FeaturePositionAssignerAgent).assign(state)

    _fpa = result.get("feature_position_assignments", {})
    _fpa_summary = {
        fid: {k: v for k, v in d.items() if v is not None}
        for fid, d in _fpa.items() if isinstance(d, dict)
    }
    from src.config.loader import get_config as _gc
    _trace = _make_trace(
        agent="feature_position_assigner", step=_step,
        input_data={"feature_assignments": list(state.get("feature_assignments", {}).keys())},
        output_data={"positions": len(_fpa), "details": _fpa_summary},
        start_time=_t0, model=_gc().models.position_assigner,
        raw_response=get_raw_response(FeaturePositionAssignerAgent),
    )
    result["agent_traces"] = [_trace]
    return result


def part_position_assigner_node(state: PipelineState) -> dict:
    """Assign face, alignment, distance, and gap to add-operation parts.

    Part of the Häppchen pipeline: Feature Tagger → Feature Assigner →
    Feature Position Assigner → **Part Position Assigner** → Blueprint Assembler.
    Only handles add-operation parts (plates, boxes, extrusions).
    Supports floating parts (distance_mm) and gaps between parts (gap_mm).
    Skipped by Agent Dispatcher if no add-operation parts detected.
    """
    active = state.get("active_agents", [])
    if active and "part_position_assigner" not in active:
        log.info("node_part_position_assigner_skipped", reason="not_in_active_agents")
        return {"part_position_assignments": {}}

    _spec = state.get("specification", state.get("description", ""))
    log.info("node_part_position_assigner", spec=_spec[:60])
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1
    result = get_agent(PartPositionAssignerAgent).assign(state)

    _ppa = result.get("part_position_assignments", {})

    # Fallback: if Part Position Assigner returned 0 positions for add-parts, generate defaults
    _fa = state.get("feature_assignments", {})
    if not _ppa and _fa:
        from src.agents.part_position_assigner import _is_part_position_target
        add_parts = {fid: d for fid, d in _fa.items() if _is_part_position_target(fid, d)}
        if add_parts:
            log.warning("part_position_empty_fallback", part_count=len(add_parts))
            _ppa = {}
            for fid in add_parts:
                _ppa[fid] = {
                    "face": ">Z", "alignment": "centered",
                    "offset_x": None, "offset_y": None,
                    "orientation_hint": None, "face_hint": None,
                    "distance_mm": None, "gap_mm": None, "relative_to": None,
                }
            result["part_position_assignments"] = _ppa

    _ppa_summary = {
        fid: {k: v for k, v in d.items() if v is not None}
        for fid, d in _ppa.items() if isinstance(d, dict)
    }
    from src.config.loader import get_config as _gc
    _trace = _make_trace(
        agent="part_position_assigner", step=_step,
        input_data={"feature_assignments": list(state.get("feature_assignments", {}).keys())},
        output_data={"positions": len(_ppa), "details": _ppa_summary},
        start_time=_t0, model=_gc().models.position_assigner,
        raw_response=get_raw_response(PartPositionAssignerAgent),
    )
    result["agent_traces"] = [_trace]
    return result


def position_assigner_node(state: PipelineState) -> dict:
    """LEGACY: Combined position assigner node. Kept for backward compatibility.

    In the new architecture, this node is not used. Feature Position Assigner
    and Part Position Assigner handle the split responsibilities.
    """
    log.warning("position_assigner_node_legacy_called")
    return {"position_assignments": {}}


def blueprint_assembler_node(state: PipelineState) -> dict:
    """Deterministic blueprint assembly from pre-assigned features.

    Part of the Häppchen pipeline: Feature Tagger → Feature Assigner →
    Position Assigner → **Blueprint Assembler** → Planner (review).
    No LLM call — pure arithmetic and graph operations.
    """
    log.info("node_blueprint_assembler",
             features=len(state.get("feature_assignments", {})))
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1
    result = get_agent(BlueprintAssembler).assemble(state)
    _trace = _make_trace(
        agent="blueprint_assembler", step=_step,
        input_data={
            "feature_assignments": list(state.get("feature_assignments", {}).keys()),
            "feature_position_assignments": list(state.get("feature_position_assignments", {}).keys()),
            "part_position_assignments": list(state.get("part_position_assignments", {}).keys()),
        },
        output_data={
            "build_order": result.get("blueprint", {}).get("build_order", []),
            "features": len(result.get("blueprint", {}).get("features", {})),
        },
        start_time=_t0,
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
    """Pass-through node: blueprint from BlueprintAssembler goes through as-is.

    The Planner LLM is no longer called for fresh requests. The Häppchen
    specialists (Feature Assigner, Position Assigner, Blueprint Assembler)
    produce the blueprint. Validation errors are routed back to the
    responsible specialist agent, not to a generalist Planner.

    For modification flow (legacy path via prompt_assembler), the Planner
    LLM is still used to patch the previous blueprint.

    PlannerAgent and its prompt are preserved in the codebase for the
    modification flow and potential future use.
    """
    change_desc = state.get("change_description", "")
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1

    # ── Modification flow: Planner LLM patches the previous blueprint ──
    if change_desc:
        log.info("node_planner", mode="patch", change=change_desc[:80])
        coord_issues = state.get("coordinate_validation_issues", "")
        if coord_issues and not state.get("plan_validation_issues"):
            state = {**state, "plan_validation_issues": coord_issues}

        _planner = get_agent(PlannerAgent)
        _prev_blueprint = state.get("blueprint", {})
        try:
            result = _planner.run(state)
        except ValueError as e:
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

        result["validator_feedback"] = ""
        result["plan_validation_issues"] = ""
        result["coordinate_validation_issues"] = ""
        result["plan_valid"] = False

        from src.config.loader import get_config as _gc
        _raw = getattr(getattr(_planner, "_rag", None), "last_chunks_used", [])
        _rag_chunks = _raw if isinstance(_raw, list) else []
        if not _rag_chunks and state.get("assembled_system_prompt", ""):
            _raw2 = getattr(
                getattr(get_agent(PromptAssembler), "_planner_rag", None),
                "last_chunks_used", []
            )
            _rag_chunks = _raw2 if isinstance(_raw2, list) else []
        _trace = _make_trace(
            agent="planner", step=_step,
            input_data={
                "specification": state.get("specification", ""),
                "change_description": change_desc,
            },
            output_data=result.get("blueprint", {}),
            start_time=_t0, model=_gc().models.planner,
            revision=True, rag_chunks_used=_rag_chunks,
            raw_response=get_raw_response(PlannerAgent),
        )
        result["agent_traces"] = [_trace]
        return result

    # ── Fresh request: pure pass-through ──
    log.info("node_planner_passthrough",
             features=len(state.get("blueprint", {}).get("features", {})))
    _trace = _make_trace(
        agent="planner", step=_step,
        input_data={"mode": "passthrough"},
        output_data=state.get("blueprint", {}),
        start_time=_t0,
    )
    return {
        "validator_feedback": "",
        "plan_validation_issues": "",
        "coordinate_validation_issues": "",
        "plan_valid": False,  # let plan_validator run fresh
        "agent_traces": [_trace],
    }


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

    mode = result.get("generation_mode", "llm")
    _trace = _make_trace(
        agent="function_decomposer", step=_step,
        input_data={"build_order": blueprint.get("build_order", [])},
        output_data={
            "generation_mode": mode,
            "code_lines": len(result.get("code", "").splitlines()),
            "skeleton_lines": len(result.get("code_skeleton", "").splitlines()),
        },
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

    In Häppchen mode (specialized agents produced the blueprint), the LLM validator
    is skipped — the specialized agents already validated structure and positions.
    Only the deterministic quick_check runs (for Feature Tree: skipped entirely).
    """
    blueprint = state.get("blueprint", {})
    spec = state.get("specification") or state.get("description", "")
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1

    # Häppchen pass-through: specialized agents already validated the blueprint.
    # The 9b LLM validator causes false positives (e.g. rejecting add-operation
    # features smaller than parent) which route to Planner and override clean work.
    _haeppchen = (bool(state.get("feature_assignments"))
                  and not state.get("change_description")
                  and not state.get("validator_feedback"))
    if _haeppchen:
        log.info("node_plan_validator_passthrough",
                 features=len(blueprint.get("features", {})))
        _trace = _make_trace(
            agent="plan_validator", step=_step,
            input_data={"mode": "häppchen_passthrough"},
            output_data={"is_valid": True, "source": "häppchen_passthrough"},
            start_time=_t0,
        )
        return {"plan_valid": True, "agent_traces": [_trace]}

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
        raw_response=get_raw_response(PlanValidatorAgent),
    )
    result["agent_traces"] = [_trace]
    return result
