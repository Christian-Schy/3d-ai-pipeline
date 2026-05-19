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

from src.config.loader import get_config
from src.graph.state import PipelineState

log = structlog.get_logger()


def route_after_entry_router(state: PipelineState) -> str:
    """After entry_router: image → visioner, everything else → interpreter (new 3-step chain).

    Modifications go through the new chain just like fresh runs — the modification
    digest (change_description + previous_blueprint) is passed as additional context
    into Inventar / Teil-Definierer so they can extend the existing blueprint.
    """
    image_path = state.get("image_path", "")
    if image_path:
        log.info("route_entry_router", decision="visioner", mode="image")
        return "visioner"
    mode = "modification" if state.get("change_description") else (
        "modify_as_fresh" if state.get("modification", "") else "fresh"
    )
    log.info("route_entry_router", decision="interpreter", mode=mode)
    return "interpreter"

# Hard limits — read from config, never hardcoded
def _max_attempts() -> int:
    return get_config().error_loop.max_attempts

def _max_semantic_retries() -> int:
    return get_config().error_loop.max_semantic_retries

def _coder_disabled() -> bool:
    return get_config().error_loop.disable_coder

# Keep module-level names for tests that import them directly
MAX_ATTEMPTS = 6
MAX_SEMANTIC_RETRIES = 2


def route_after_executor(state: PipelineState) -> str:
    """After Executor: success → validator, failure → error_router.

    Template-mode runs bypass the Coder/code_fixer error loop entirely:
    if every feature is template-generated, the failure is a deterministic
    bug (codegen, geometry, blueprint) — the Coder cannot diagnose it and
    historically rewrites correct template code into broken code (e.g.
    losing the assemble() wrapper, see run f3251fa6). Fail-fast surfaces
    the real error instead of burying it under LLM repair attempts.
    """
    has_error = bool(state.get("execution_error") or state.get("validation_error"))

    if not has_error:
        log.info("route_executor", decision="validator")
        return "validator"

    if state.get("generation_mode") == "template":
        log.warning("route_executor", decision="end",
                    reason="template_mode_no_coder_repair",
                    error=(state.get("execution_error")
                           or state.get("validation_error", ""))[:120])
        return "end"

    if _coder_disabled():
        log.warning("route_executor", decision="end",
                    reason="coder_disabled",
                    error=(state.get("execution_error")
                           or state.get("validation_error", ""))[:120])
        return "end"

    if state.get("attempts", 0) >= _max_attempts():
        log.warning("route_executor", decision="end", reason="max_attempts")
        return "end"

    log.info("route_executor", decision="error_router",
             error=state.get("execution_error", "")[:60])
    return "error_router"


_PLACEMENT_ERROR_KEYWORDS = (
    "position", "offset", "floating", "centered", "misplaced", "placement",
    "wrong place", "not centered", "too far", "falsch platziert",
    "verschoben", "falsche position", "nicht zentriert", "falsch positioniert",
    "schweben", "zu weit", "wrong offset", "wrong location",
)

# Dimension-level errors — wrong raw_params on a part. Can only be fixed by
# re-running Inventar (feature_definierer doesn't regenerate raw_params).
_DIMENSION_ERROR_KEYWORDS = (
    "dimension", "x-dimension", "y-dimension", "z-dimension",
    "dim x", "dim y", "dim z", "bbox", "bounding",
    "breite falsch", "laenge falsch", "länge falsch", "hoehe falsch", "höhe falsch",
    "statt 50mm", "statt 40mm", "statt 30mm", "statt 20mm", "statt 100mm",
    "zu klein", "zu gross", "zu groß",
)


def route_after_validator(state: PipelineState) -> str:
    """After Validator: ok → end, placement error → coder, dimension error → inventar, other blueprint error → feature_definierer."""
    feedback = state.get("validator_feedback", "")

    if not feedback:
        log.info("route_validator", decision="end")
        return "end"

    semantic_attempts = state.get("semantic_attempts", 0)
    if semantic_attempts >= _max_semantic_retries():
        log.warning("route_validator", decision="end",
                    reason="max_semantic_retries", attempts=semantic_attempts)
        return "end"

    feedback_lower = feedback.lower()

    # Placement/position errors: coder generated wrong offset. Route to coder.
    if any(kw in feedback_lower for kw in _PLACEMENT_ERROR_KEYWORDS):
        if _coder_disabled():
            log.warning("route_validator", decision="end",
                        reason="placement_error_coder_disabled",
                        feedback=feedback[:80])
            return "end"
        log.info("route_validator", decision="coder",
                 reason="placement_error", feedback=feedback[:80])
        return "coder"

    # Dimension errors: Inventar produced wrong raw_params. Only Inventar can fix.
    if any(kw in feedback_lower for kw in _DIMENSION_ERROR_KEYWORDS):
        log.info("route_validator", decision="inventar",
                 reason="dimension_error", feedback=feedback[:80],
                 semantic_attempts=semantic_attempts)
        return "inventar"

    # Blueprint-level errors: retry at feature_definierer (redo features + placement).
    log.info("route_validator", decision="feature_definierer",
             semantic_attempts=semantic_attempts,
             feedback=feedback[:60])
    return "feature_definierer"


def route_after_error_router(state: PipelineState) -> str:
    """After ErrorRouter: pick the repair strategy based on current phase.

    Phase 1 → coder       (Coder fixes its own code, attempts 1-2)
    Phase 2 → code_fixer  (CodeFixer diagnoses, then Coder retries, attempts 3-4)
    Phase 3 → end         (give up)
    """
    phase = state.get("phase", 1)

    if _coder_disabled():
        log.warning("route_error_router", decision="end",
                    reason="coder_disabled", phase=phase)
        return "end"

    if phase == 1:
        log.info("route_error_router", decision="coder", phase=1)
        return "coder"
    elif phase == 2:
        log.info("route_error_router", decision="code_fixer", phase=2)
        return "code_fixer"
    else:
        log.warning("route_error_router", decision="end", phase=phase)
        return "end"
