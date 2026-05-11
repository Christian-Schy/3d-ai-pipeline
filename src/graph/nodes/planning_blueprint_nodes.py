"""Planning node subset split out from planning_nodes.py."""
from __future__ import annotations
import time
import structlog

from src.graph.state import PipelineState
from src.agents.blueprint_architect import BlueprintArchitect
from src.agents.function_decomposer import FunctionDecomposerAgent
from src.graph.feature_tree import FeatureTree
from . import _registry
from ._tracing import _make_trace

log = structlog.get_logger()

# ══════════════════════════════════════════════════════════════════
# Blueprint Architect (monolithisch — Fallback für Fix/Modify)
# ══════════════════════════════════════════════════════════════════

def blueprint_architect_node(state: PipelineState) -> dict:
    """Generate a complete Feature Tree Blueprint in a single LLM call.

    Replaces the Häppchen chain (Feature Tagger → Feature Assigner →
    Feature Position Assigner → Part Position Assigner → Blueprint Assembler).

    Handles three modes:
      - Fresh:  spec → new blueprint
      - Modify: spec + change_description + previous_blueprint → updated blueprint
      - Fix:    spec + validation errors + broken blueprint → corrected blueprint
    """
    spec = state.get("specification", state.get("description", ""))
    change_desc = state.get("change_description", "")
    prev_blueprint = state.get("blueprint", {}) or state.get("previous_blueprint", {})
    validation_issues = (
        state.get("coordinate_validation_issues", "")
        or state.get("plan_validation_issues", "")
        or state.get("validator_feedback", "")
    )

    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1
    architect = _registry.get_agent(BlueprintArchitect)

    try:
        # Mode selection
        if validation_issues and prev_blueprint:
            # Fix mode: re-route after validation failure
            log.info("node_blueprint_architect", mode="fix",
                     issues=validation_issues[:80])
            result = architect.fix(spec, prev_blueprint, validation_issues)
        elif change_desc and prev_blueprint:
            # Modify mode: apply changes to existing blueprint
            log.info("node_blueprint_architect", mode="modify",
                     change=change_desc[:80])
            result = architect.modify(spec, change_desc, prev_blueprint)
        else:
            # Fresh mode: generate from scratch
            log.info("node_blueprint_architect", mode="fresh",
                     spec=spec[:80])
            result = architect.generate(spec)

        blueprint = result["blueprint"]
        rag_chunks = result.get("rag_chunks_used", [])

    except ValueError as e:
        log.error("node_blueprint_architect_failed", error=str(e)[:200])
        _trace = _make_trace(
            agent="blueprint_architect", step=_step,
            input_data={"specification": spec},
            output_data={"error": str(e)[:200]},
            start_time=_t0,
        )
        return {
            "blueprint": prev_blueprint or {},
            "plan_valid": False,
            "plan_validation_issues": f"Blueprint Architect error: {str(e)[:150]}",
            "agent_traces": [_trace],
        }

    from src.config.loader import get_config as _gc
    _trace = _make_trace(
        agent="blueprint_architect", step=_step,
        input_data={"specification": spec, "mode": "fix" if validation_issues else ("modify" if change_desc else "fresh")},
        output_data={
            "build_order": blueprint.get("build_order", []),
            "features": len(blueprint.get("features", {})),
        },
        start_time=_t0,
        model=_gc().models.blueprint_architect,
        rag_chunks_used=rag_chunks,
        raw_response=getattr(architect, "_last_raw_response", None),
    )

    return {
        "blueprint": blueprint,
        "plan_valid": False,  # let validators run
        "plan_validation_issues": "",
        "coordinate_validation_issues": "",
        "validator_feedback": "",
        "agent_traces": [_trace],
    }


def blueprint_resolver_node(state: PipelineState) -> dict:
    """Deterministic: convert semantic blueprint → resolved blueprint.

    Handles orientation resolution (hochkant → dimension swap),
    face calculation (rechts → >X), and offset computation
    (flush_right → numeric offset). No LLM needed.

    Sits between blueprint_architect and coordinate_validator.
    If the blueprint is already resolved (legacy format), passes through.
    """
    blueprint = state.get("blueprint", {})
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1

    if not blueprint or not blueprint.get("features"):
        return {"agent_traces": [_make_trace(
            agent="blueprint_resolver", step=_step,
            input_data={}, output_data={"skipped": True, "reason": "no_blueprint"},
            start_time=_t0,
        )]}

    from src.tools.blueprint_resolver import resolve_blueprint

    # resolve_blueprint handles all cases internally:
    # - Semantic format → full resolution (orientation + face + offsets)
    # - Already-resolved legacy → passthrough
    # - Mixed fix-mode → orientation resolution only, keep existing placement
    resolved = resolve_blueprint(blueprint)

    # Log what changed
    changes = []
    for fid, feat in resolved.get("features", {}).items():
        orig = blueprint.get("features", {}).get(fid, {})
        orig_params = orig.get("params", {})
        new_params = feat.get("params", {})
        if orig_params != new_params:
            changes.append(f"{fid}: params changed (orientation resolved)")
        placement = feat.get("placement")
        if placement and (placement.get("offset_x", 0) != 0 or placement.get("offset_y", 0) != 0):
            changes.append(f"{fid}: offsets computed ({placement['offset_x']}, {placement['offset_y']})")

    log.info("node_blueprint_resolver",
             features=len(resolved.get("features", {})),
             changes=len(changes))

    _trace = _make_trace(
        agent="blueprint_resolver", step=_step,
        input_data={"build_order": blueprint.get("build_order", [])},
        output_data={
            "features_resolved": len(resolved.get("features", {})),
            "changes": changes[:10],  # limit trace size
        },
        start_time=_t0,
    )

    return {
        "blueprint": resolved,
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

    result = _registry.get_agent(FunctionDecomposerAgent).decompose(state)

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


