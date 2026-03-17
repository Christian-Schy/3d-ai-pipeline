"""Input nodes: entry_router_node and interpreter_node."""
from __future__ import annotations
import time
import structlog
from langgraph.types import interrupt
from langchain_core.messages import AIMessage, HumanMessage

from src.graph.state import PipelineState
from src.agents.interpreter import InterpreterAgent
from src.agents.modification_interpreter import ModificationInterpreterAgent
from ._registry import get_agent
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
    """Refine the user request into a complete specification via dialog.

    If the request is already complete: writes specification and continues.
    If information is missing: interrupts the graph and asks a question.

    How interrupt() works:
      interrupt(question) pauses the graph and returns the question to the caller.
      The caller (main.py / app.py) shows the question, gets the user answer,
      then resumes the graph with: graph.invoke(Command(resume=answer), config)
      The graph continues from exactly this point with the answer as return value.
    """
    messages = state.get("messages", [])
    log.info("node_interpreter", description=state["description"][:60],
             messages_so_far=len(messages))

    # Hard limit: after 2 Q&A rounds (4 messages) stop asking and build the best spec
    MAX_QA_ROUNDS = 2
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1
    _interpreter = get_agent(InterpreterAgent)
    if len(messages) >= MAX_QA_ROUNDS * 2:
        log.info("node_interpreter_forced_complete",
                 reason="max_qa_rounds_reached", messages=len(messages))
        description = state.get("description", "")
        history = _interpreter._format_history(messages)
        spec = f"{description}. Additional context: {history}" if history else description
        from src.config.loader import get_config as _gc
        _trace = _make_trace(
            agent="interpreter", step=_step,
            input_data=description,
            output_data={"specification": spec, "is_complete": True},
            start_time=_t0, model=_gc().models.interpreter,
        )
        return {"specification": spec, "is_complete": True, "agent_traces": [_trace]}

    result = _interpreter.process(state)

    if result["is_complete"]:
        from src.config.loader import get_config as _gc
        _raw = getattr(getattr(_interpreter, "_rag", None), "last_chunks_used", [])
        _rag_chunks = _raw if isinstance(_raw, list) else []
        _trace = _make_trace(
            agent="interpreter", step=_step,
            input_data=state.get("description", ""),
            output_data={"specification": result["specification"], "is_complete": True},
            start_time=_t0, model=_gc().models.interpreter,
            rag_chunks_used=_rag_chunks,
        )
        return {
            "specification": result["specification"],
            "is_complete": True,
            "agent_traces": [_trace],
        }

    # Not complete — ask the user a clarifying question
    # interrupt() pauses the graph here and returns the question to the caller
    user_answer = interrupt(result["question"])

    # Graph resumes here with the user's answer
    # Add both question and answer to the message history
    return {
        "messages": [
            AIMessage(content=result["question"]),
            HumanMessage(content=user_answer),
        ],
        "is_complete": False,
        # Node returns — graph re-evaluates: interpreter_node runs again
        # with the extended message history
    }
