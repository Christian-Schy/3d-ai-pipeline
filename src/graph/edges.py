"""
src/graph/edges.py — All routing decisions for the pipeline graph.

Routing is pure logic — no LLM calls here.
Each function reads the current state and returns the name of the next node.

Flow overview:
  interpreter → planner → coder → executor
                                       ↓
                            route_after_executor
                           /                    \\
                      "error"               "validator"
                          ↓                      ↓
                  error_router_node       validator_node
                          ↓                      ↓
               route_after_error_router   route_after_validator
               /           |         \\    /              \\
           "coder"  "code_fixer"   "end" "end"         "planner"
"""

import structlog
from src.graph.state import PipelineState
from src.config.loader import get_config


log = structlog.get_logger()


def route_after_entry_router(state: PipelineState) -> str:
    """After entry_router: modification → task_classifier, image → visioner, fresh → interpreter.

    Modifications go through task_classifier for a focused Planner prompt.
    If modification_interpreter classified as new request, skip interpreter and
    go to task_classifier for a fresh build (avoids questions about visible model).
    """
    change_desc = state.get("change_description", "")
    image_path = state.get("image_path", "")
    if change_desc:
        log.info("route_entry_router", decision="task_classifier", mode="modification")
        return "task_classifier"
    if image_path:
        log.info("route_entry_router", decision="visioner", mode="image")
        return "visioner"
    if state.get("modification", ""):
        log.info("route_entry_router", decision="task_classifier", mode="modify_as_fresh")
        return "task_classifier"
    log.info("route_entry_router", decision="interpreter", mode="fresh")
    return "interpreter"

# Hard limits — read from config, never hardcoded
def _max_attempts() -> int:
    return get_config().error_loop.max_attempts

def _max_semantic_retries() -> int:
    return get_config().error_loop.max_semantic_retries

# Keep module-level names for tests that import them directly
MAX_ATTEMPTS = 6
MAX_SEMANTIC_RETRIES = 2


def route_after_executor(state: PipelineState) -> str:
    """After Executor: success → validator, failure → error_router."""
    has_error = bool(state.get("execution_error") or state.get("validation_error"))

    if not has_error:
        log.info("route_executor", decision="validator")
        return "validator"

    if state.get("attempts", 0) >= _max_attempts():
        log.warning("route_executor", decision="end", reason="max_attempts")
        return "end"

    log.info("route_executor", decision="error_router",
             error=state.get("execution_error", "")[:60])
    return "error_router"


def route_after_validator(state: PipelineState) -> str:
    """After Validator: ok → end, not ok → planner (max 2x) or end."""
    feedback = state.get("validator_feedback", "")

    if not feedback:
        # validator_feedback is empty = validator said OK
        log.info("route_validator", decision="end")
        return "end"

    semantic_attempts = state.get("semantic_attempts", 0)
    if semantic_attempts >= _max_semantic_retries():
        log.warning("route_validator", decision="end",
                    reason="max_semantic_retries", attempts=semantic_attempts)
        return "end"

    log.info("route_validator", decision="planner",
             semantic_attempts=semantic_attempts,
             feedback=feedback[:60])
    return "planner"


def route_after_error_router(state: PipelineState) -> str:
    """After ErrorRouter: pick the repair strategy based on current phase.

    Phase 1 → coder       (Coder fixes its own code, attempts 1-2)
    Phase 2 → code_fixer  (CodeFixer diagnoses, then Coder retries, attempts 3-4)
    Phase 3 → end         (give up)
    """
    phase = state.get("phase", 1)

    if phase == 1:
        log.info("route_error_router", decision="coder", phase=1)
        return "coder"
    elif phase == 2:
        log.info("route_error_router", decision="code_fixer", phase=2)
        return "code_fixer"
    else:
        log.warning("route_error_router", decision="end", phase=phase)
        return "end"
