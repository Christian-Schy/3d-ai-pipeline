"""Input nodes: entry_router_node and interpreter_node."""
from __future__ import annotations
import time
import structlog
from langgraph.types import interrupt
from langchain_core.messages import AIMessage, HumanMessage

from src.graph.state import PipelineState
from src.agents.interpreter import InterpreterAgent
from src.agents.modification_interpreter import ModificationInterpreterAgent
from ._registry import get_agent, get_raw_response
from ._tracing import _make_trace

log = structlog.get_logger()


def entry_router_node(state: PipelineState) -> dict:
    """Decide if this is a fresh request or a modification of the previous model.

    Reads the 'modification' field from state.
    If set + previous_blueprint exists: classifies via ModificationInterpreterAgent.
    Result is stored as 'change_description' — Planner reads this in patch mode.
    """
    modification = state.get("modification", "")
    previous_blueprint = state.get("previous_blueprint", {})
    image_path = state.get("image_path", "")

    if not modification or not previous_blueprint:
        mode = "image" if image_path else "fresh"
        log.info("node_entry_router", mode=mode,
                 has_modification=bool(modification),
                 has_previous_blueprint=bool(previous_blueprint),
                 has_image=bool(image_path))
        return {"change_description": ""}

    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1
    result = get_agent(ModificationInterpreterAgent).classify(state)
    from src.config.loader import get_config as _gc
    _mod_trace = _make_trace(
        agent="modification_interpreter", step=_step,
        input_data={"modification": modification},
        output_data=result,
        start_time=_t0, model=_gc().models.modification_interpreter,
        raw_response=get_raw_response(ModificationInterpreterAgent),
    )
    if result["is_modification"]:
        log.info("node_entry_router", mode="modification",
                 change=result["change_description"][:80])
        return {
            "change_description": result["change_description"],
            "is_additive":        result.get("is_additive", False),
            # Set description to modification so Interpreter sees it
            "description": modification,
            "agent_traces": [_mod_trace],
        }
    else:
        log.info("node_entry_router", mode="new_request")
        return {
            "change_description": "",
            "description": modification,
            # Clear previous context for fresh run
            "previous_blueprint": {},
            "previous_stl_path": "",
            "agent_traces": [_mod_trace],
        }


def interpreter_node(state: PipelineState) -> dict:
    """Pass raw user description through as specification (raw-text mode).

    The Interpreter currently operates in pass-through mode: no LLM call,
    no clarifying dialog. The raw description becomes the specification directly.

    The full dialog infrastructure (InterpreterAgent, interrupt(), message history)
    is preserved in the codebase for future reactivation when the Interpreter
    gets a specialized role (e.g. ambiguity resolution, unit normalization).
    """
    description = state.get("description", "")
    log.info("node_interpreter_passthrough", description=description[:60])

    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1
    _trace = _make_trace(
        agent="interpreter", step=_step,
        input_data=description,
        output_data={"specification": description, "is_complete": True, "mode": "passthrough"},
        start_time=_t0,
    )
    return {
        "specification": description,
        "is_complete": True,
        "agent_traces": [_trace],
    }
