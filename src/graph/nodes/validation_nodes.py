"""Validation nodes: validator_node and error_router_node."""
from __future__ import annotations
import time
import structlog

from src.graph.state import PipelineState
from src.agents.validator import ValidatorAgent
from ._registry import get_agent
from ._tracing import _make_trace

log = structlog.get_logger()


def validator_node(state: PipelineState) -> dict:
    """Check the finished STL: geometry correctness + semantic match to intent.

    Geometry (trimesh): watertight, volume, dimension cross-check vs Blueprint.
    Semantic (LLM):     does the model match what the user described?

    If not OK: writes validator_feedback for the Planner and increments
    semantic_attempts. The Planner gets at most 2 chances (see edges.py).
    """
    log.info("node_validator",
             stl_path=state.get("stl_path", ""),
             semantic_attempts=state.get("semantic_attempts", 0))

    # Volume-delta context: let validator know what volume change to expect
    blueprint = state.get("blueprint", {})
    prev_stats = state.get("validator_stats", {})
    if prev_stats.get("volume_mm3") and state.get("change_description"):
        blueprint = dict(blueprint)  # shallow copy — don't mutate original
        blueprint["_prev_volume_mm3"] = prev_stats["volume_mm3"]
        blueprint["_expected_volume_change"] = state.get("is_additive", False)

    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1
    result = get_agent(ValidatorAgent).check({**state, "blueprint": blueprint})

    from src.config.loader import get_config as _gc
    if result.ok:
        _trace = _make_trace(
            agent="validator", step=_step,
            input_data={"spec": state.get("specification", ""),
                        "stl_path": state.get("stl_path", "")},
            output_data={"is_valid": True, "stats": result.stats},
            start_time=_t0, model=_gc().models.validator,
        )
        # Preserve the successful blueprint, code, and STL path for iterative editing
        return {
            "validator_feedback": "",
            "previous_blueprint": state.get("blueprint", {}),
            "previous_code": state.get("code", ""),
            "previous_stl_path": state.get("stl_path", ""),
            "validator_stats": result.stats,  # size_mm, volume_mm3 → 3D viewer
            "agent_traces": [_trace],
        }
    else:
        new_semantic_attempts = state.get("semantic_attempts", 0) + 1
        log.warning("node_validator_fail",
                    semantic_attempts=new_semantic_attempts,
                    feedback=result.feedback[:80])
        _trace = _make_trace(
            agent="validator", step=_step,
            input_data={"spec": state.get("specification", ""),
                        "stl_path": state.get("stl_path", "")},
            output_data={"is_valid": False, "feedback": result.feedback},
            start_time=_t0, model=_gc().models.validator,
        )
        return {
            "validator_feedback": result.feedback,
            "semantic_attempts": new_semantic_attempts,
            "agent_traces": [_trace],
        }


def error_router_node(state: PipelineState) -> dict:
    """Increment attempt counter and determine the repair phase.

    Phase 1 (attempts 1-2): Coder fixes its own code.
    Phase 2 (attempts 3-4): CodeFixer diagnoses, then Coder retries.
    Phase 3 (attempts 5+):  Give up.

    The phase is just a number — routing decisions live in edges.py.
    """
    attempts = state.get("attempts", 0) + 1
    phase = 1 if attempts <= 2 else (2 if attempts <= 4 else 3)

    log.info("node_error_router", attempts=attempts, phase=phase,
             error=state.get("execution_error", "")[:60])

    return {"attempts": attempts, "phase": phase}
