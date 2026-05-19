"""Validation nodes: validator_node and error_router_node."""
from __future__ import annotations

import time

import structlog

from src.agents.validator import ValidatorAgent
from src.graph.state import PipelineState

from ._registry import get_agent, get_raw_response
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
            raw_response=get_raw_response(ValidatorAgent),
        )

        # Auto-learn: save successful blueprint→code pair as a new RAG example.
        # Non-blocking — a RAG failure must never fail the pipeline.
        try:
            from src.rag.coder_rag import CoderRAG
            _rag = CoderRAG()
            _saved = _rag.save_successful_code(
                blueprint=state.get("blueprint", {}),
                code=state.get("code", ""),
            )
            if _saved:
                log.info("rag_auto_learn_saved",
                         description=(state.get("blueprint") or {}).get("description", "")[:60])
        except Exception as _rag_err:
            log.warning("rag_auto_learn_failed", error=str(_rag_err))

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
            raw_response=get_raw_response(ValidatorAgent),
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

    Also detects when the same geometry error repeats across attempts
    and injects a strategy-change hint into fix_plan.
    """
    attempts = state.get("attempts", 0) + 1
    phase = 1 if attempts <= 2 else (2 if attempts <= 4 else 3)

    current_error = state.get("validation_error", "") or state.get("execution_error", "")
    prev_error = state.get("previous_validation_error", "")

    result = {
        "attempts": attempts,
        "phase": phase,
        "code_review_attempts": 0,
        "previous_validation_error": current_error,
    }

    # Detect repeated geometry errors — same error type 2+ times means
    # the coder's approach is fundamentally flawed, not just a typo.
    if (current_error and prev_error
            and "watertight" in current_error.lower()
            and "watertight" in prev_error.lower()):
        strategy_hint = (
            "\n\n★ WIEDERHOLTER GEOMETRY-ERROR: Non-manifold Mesh tritt wiederholt auf.\n"
            "Das ist ein CadQuery/OCCT Tessellation-Problem, KEIN Code-Fehler.\n"
            "Strategie-Wechsel:\n"
            "1. .clean() nach JEDER .union() und .cut() Operation\n"
            "2. Keine exakte Kantenkontakt-Geometrie — 0.01mm Inset bei flush edges\n"
            "3. Alternativ: Basis + Aufsatz als face-based .extrude() statt separate box + union\n"
            "4. Export mit engerer Toleranz: cq.exporters.export(result, OUTPUT_PATH, tolerance=0.001)"
        )
        existing_fix = state.get("fix_plan", "")
        result["fix_plan"] = existing_fix + strategy_hint
        log.warning("error_router_repeated_geometry",
                    attempts=attempts, hint="watertight_strategy_change")

    log.info("node_error_router", attempts=attempts, phase=phase,
             error=current_error[:60])

    return result
