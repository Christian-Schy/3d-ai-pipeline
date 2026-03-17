"""
src/graph/pipeline.py — Assembles the LangGraph and exposes run().

Stufe 4 additions:
  - MemorySaver checkpointer so interrupt() can freeze/resume state
  - interpreter_node loops back to itself until is_complete=True
  - run() replaced by PipelineRunner class which handles the dialog loop
"""

import uuid
import structlog
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from src.graph.state import PipelineState
from src.graph.nodes import (
    entry_router_node,
    visioner_node,
    interpreter_node,
    task_classifier_node,
    prompt_assembler_node,
    plan_validator_node,
    planner_node,
    coder_node,
    executor_node,
    validator_node,
    error_router_node,
    code_fixer_node,
)
from src.graph.edges import (
    route_after_entry_router,
    route_after_executor,
    route_after_validator,
    route_after_error_router,
)

log = structlog.get_logger()


def route_after_interpreter(state: PipelineState) -> str:
    """After interpreter: complete → task_classifier, not complete → loop back."""
    if state.get("is_complete"):
        return "task_classifier"
    return "interpreter"  # run interpreter again with extended message history


def route_after_plan_validator(state: PipelineState) -> str:
    """After plan_validator: valid → coder, invalid → planner (up to max_retries)."""
    from src.config.loader import get_config
    if state.get("plan_valid", True):
        return "coder"
    max_retries = get_config().plan_validator.max_retries
    if state.get("plan_validation_attempts", 0) >= max_retries:
        log.warning("route_plan_validator", decision="coder",
                    reason="max_retries_exceeded",
                    attempts=state.get("plan_validation_attempts"))
        return "coder"  # give up validating, let Coder try
    log.info("route_plan_validator", decision="planner",
             issues=state.get("plan_validation_issues", "")[:60])
    return "planner"


def build_graph() -> StateGraph:
    """Construct and compile the pipeline graph with checkpointing."""
    # MemorySaver is created here (inside build_graph, not at module level)
    # so importing pipeline.py in tests costs nothing.
    checkpointer = MemorySaver()

    graph = StateGraph(PipelineState)

    graph.add_node("entry_router", entry_router_node)
    graph.add_node("visioner", visioner_node)
    graph.add_node("interpreter", interpreter_node)
    graph.add_node("task_classifier", task_classifier_node)
    graph.add_node("prompt_assembler", prompt_assembler_node)
    graph.add_node("plan_validator", plan_validator_node)
    graph.add_node("planner", planner_node)
    graph.add_node("coder", coder_node)
    graph.add_node("executor", executor_node)
    graph.add_node("validator", validator_node)
    graph.add_node("error_router", error_router_node)
    graph.add_node("code_fixer", code_fixer_node)

    graph.set_entry_point("entry_router")

    # Entry router: modification → task_classifier, fresh → interpreter
    graph.add_conditional_edges(
        "entry_router",
        route_after_entry_router,
        {
            "task_classifier": "task_classifier",
            "interpreter": "interpreter",
            "visioner": "visioner",
        },
    )

    # Interpreter loops until spec is complete, then → task_classifier
    graph.add_conditional_edges(
        "interpreter",
        route_after_interpreter,
        {"task_classifier": "task_classifier", "interpreter": "interpreter"},
    )

    # V4 chain: task_classifier → prompt_assembler → planner → plan_validator → coder
    graph.add_edge("visioner", "interpreter")
    graph.add_edge("task_classifier", "prompt_assembler")
    graph.add_edge("prompt_assembler", "planner")
    graph.add_edge("planner", "plan_validator")
    graph.add_conditional_edges(
        "plan_validator",
        route_after_plan_validator,
        {"coder": "coder", "planner": "planner"},
    )
    graph.add_edge("coder", "executor")
    graph.add_edge("code_fixer", "coder")

    graph.add_conditional_edges(
        "executor",
        route_after_executor,
        {"validator": "validator", "error_router": "error_router", "end": END},
    )
    graph.add_conditional_edges(
        "validator",
        route_after_validator,
        {"end": END, "planner": "planner"},
    )
    graph.add_conditional_edges(
        "error_router",
        route_after_error_router,
        {"coder": "coder", "code_fixer": "code_fixer", "end": END},
    )

    compiled = graph.compile(checkpointer=checkpointer)
    log.info("pipeline_built")
    return compiled


_pipeline = None


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = build_graph()
    return _pipeline


# ------------------------------------------------------------------
# PipelineRunner — handles the dialog loop externally
# ------------------------------------------------------------------

class PipelineRunner:
    """Manages a full pipeline run including the Interpreter dialog loop.

    Usage:
        runner = PipelineRunner()
        result = runner.run(
            description="a box",
            ask_user=lambda question: input(question + " ")
        )

    ask_user: a callable that receives a question string and returns
              the user's answer. For CLI: input(). For Gradio: a callback.
    """

    def __init__(self):
        self._pipeline = get_pipeline()

    def run(self, description: str, ask_user=None, thread_id: str = None,
            image_path: str = "") -> PipelineState:
        """Run the pipeline, handling any clarifying questions via ask_user.

        Args:
            description: The user's original request (can be empty if image_path set).
            ask_user:    Callable(question: str) -> str.
            thread_id:   Unique ID. Auto-generated if not provided.
            image_path:  Optional path to an image/sketch for Visioner (Stufe 8).
        """
        # Always use a fresh thread_id unless explicitly provided.
        # MemorySaver caches state per thread_id — reusing an old id would
        # make LangGraph replay the previous run's state instead of starting fresh.
        if thread_id is None:
            thread_id = f"run_{uuid.uuid4().hex[:8]}"
        self._current_thread_id = thread_id
        config = {"configurable": {"thread_id": thread_id}}

        initial_state: PipelineState = {
            "description": description,
            "raw_input": description,
            "messages": [],
            "specification": "",
            "is_complete": False,
            "blueprint": {},
            "code": "",
            "stl_path": "",
            "execution_error": "",
            "validation_error": "",
            "attempts": 0,
            "phase": 1,
            "semantic_attempts": 0,
            "validator_feedback": "",
            "fix_plan": "",
            "feedback": "",
            "modification": "",
            "image_path": image_path,
            "change_description": "",
            "previous_blueprint": {},
            "previous_code": "",
            "previous_stl_path": "",
            "validator_stats": {},
            "print_status": "",
            "is_additive": False,
            # V4 fields
            "task_classification": {},
            "assembled_system_prompt": "",
            "plan_valid": False,
            "plan_validation_issues": "",
            "plan_validation_attempts": 0,
            "geometry_state": {},
            "geometry_precheck_report": "",
            "agent_traces": [],
        }

        log.info("pipeline_run_start", description=description[:80])

        # First invocation — starts the graph
        state = self._pipeline.invoke(initial_state, config)

        # Dialog loop — runs as long as the graph is interrupted for questions
        while self._is_interrupted(config):
            if ask_user is None:
                # No dialog handler — resume with empty string to trigger fallback
                state = self._pipeline.invoke(Command(resume=""), config)
            else:
                # Get the pending question from the interrupt
                question = self._get_interrupt_value(config)
                answer = ask_user(question)
                state = self._pipeline.invoke(Command(resume=answer), config)

        # Use blueprint description as the canonical model label.
        # Without this, description stays as the raw user input ("erstelle einen würfel"),
        # which makes history labels meaningless after modifications.
        bp_desc = (state.get("blueprint") or {}).get("description", "")
        if bp_desc and state.get("stl_path"):
            state["description"] = bp_desc

        success = bool(state.get("stl_path")) and not state.get("validator_feedback")
        log.info("pipeline_run_complete",
                 success=success,
                 stl_path=state.get("stl_path"),
                 attempts=state.get("attempts"),
                 semantic_attempts=state.get("semantic_attempts"))

        return state

    def _is_interrupted(self, config: dict) -> bool:
        """Check if the graph is currently paused at an interrupt()."""
        snapshot = self._pipeline.get_state(config)
        return bool(snapshot.tasks)  # pending tasks = graph is interrupted

    def _get_interrupt_value(self, config: dict) -> str:
        """Get the question string from the current interrupt."""
        snapshot = self._pipeline.get_state(config)
        for task in snapshot.tasks:
            # interrupt value is stored in task interrupts
            if hasattr(task, "interrupts") and task.interrupts:
                return task.interrupts[0].value
        return ""


    def modify(self, modification: str, previous_state: PipelineState,
               ask_user=None, thread_id: str = None) -> PipelineState:
        """Apply a modification to an existing model.

        Takes the previous state (with previous_blueprint and previous_stl_path)
        and runs the pipeline with the modification as input.

        Args:
            modification:    What to change: "Make the hole 2mm bigger"
            previous_state:  The final state from the last successful run.
            ask_user:        Same as run() — for clarifying questions.
            thread_id:       Should match the original run's thread_id.
        """
        # Resolve previous_blueprint — validator_node stores it in
        # "previous_blueprint" after success. Fall back to "blueprint"
        # if previous_blueprint is empty (e.g. on first modify attempt).
        prev_bp = (
            previous_state.get("previous_blueprint")
            or previous_state.get("blueprint")
            or {}
        )
        prev_stl = (
            previous_state.get("previous_stl_path")
            or previous_state.get("stl_path")
            or ""
        )
        prev_code = (
            previous_state.get("previous_code")
            or previous_state.get("code")
            or ""
        )

        log.info("pipeline_modify_start",
                 modification=modification[:80],
                 has_previous_blueprint=bool(prev_bp))

        mod_state: PipelineState = {
            "description": modification,
            "raw_input": modification,
            "modification": modification,
            "messages": [],
            "specification": "",
            "is_complete": False,
            "blueprint": {},
            "code": "",
            "stl_path": "",
            "execution_error": "",
            "validation_error": "",
            "attempts": 0,
            "phase": 1,
            "semantic_attempts": 0,
            "validator_feedback": "",
            "fix_plan": "",
            "change_description": "",
            "image_path": "",
            "feedback": "",
            "previous_blueprint": prev_bp,
            "previous_code": prev_code,
            "previous_stl_path": prev_stl,
            "validator_stats": {},
            "print_status": "",
            "is_additive": False,
            # V4 fields
            "task_classification": {},
            "assembled_system_prompt": "",
            "plan_valid": False,
            "plan_validation_issues": "",
            "plan_validation_attempts": 0,
            "geometry_state": previous_state.get("geometry_state", {}),
            "geometry_precheck_report": "",
            "agent_traces": [],
        }

        # Always use a fresh thread_id — never reuse a previous run's checkpoint.
        mod_thread = f"mod_{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": mod_thread}}

        log.info("pipeline_modify_start", modification=modification[:80])
        state = self._pipeline.invoke(mod_state, config)

        while self._is_interrupted(config):
            if ask_user is None:
                state = self._pipeline.invoke(Command(resume=""), config)
            else:
                question = self._get_interrupt_value(config)
                answer = ask_user(question)
                state = self._pipeline.invoke(Command(resume=answer), config)

        # Same as run(): use blueprint description as canonical label.
        bp_desc = (state.get("blueprint") or {}).get("description", "")
        if bp_desc and state.get("stl_path"):
            state["description"] = bp_desc

        return state


def run(description: str, ask_user=None) -> PipelineState:
    """Convenience wrapper — creates a fresh PipelineRunner and runs once."""
    runner = PipelineRunner()
    return runner.run(description, ask_user=ask_user)
