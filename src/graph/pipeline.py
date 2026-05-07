"""
src/graph/pipeline.py — Assembles the LangGraph and exposes run().

Stufe 4 additions:
  - MemorySaver checkpointer so interrupt() can freeze/resume state
  - interpreter_node loops back to itself until is_complete=True
  - run() replaced by PipelineRunner class which handles the dialog loop

═══════════════════════════════════════════════════════════════════
STRUKTUR (bei Aenderungen pflegen! Siehe CLAUDE.md)
═══════════════════════════════════════════════════════════════════
Routing-Funktionen (Condition-Edges):
  route_after_interpreter             — Interpreter-Loop bis Spec komplett
  route_after_coordinate_validator    — zurueck zu feature_definierer oder architect
  route_after_code_review             — zurueck zu coder bei Issues (max 2)
  route_after_function_decomposer     — template-Modus ueberspringt Coder
  route_after_plan_validator          — zurueck zu assembly oder architect
  _is_3step_chain                     — Helper: unterscheidet Chain vs. Architect
  (in edges.py):
  route_after_entry_router            — alles → interpreter (auch Modifications)
  route_after_executor                — success → validator, fail → error_router
                                        (template-mode: fail → end, kein Coder)
  route_after_validator               — end/inventar/feature_definierer/coder
  route_after_error_router            — coder/code_fixer/end

Graph-Konstruktion:
  build_graph                         — haengt Nodes+Edges zusammen, compile
  get_pipeline                        — Singleton-Zugriff auf kompilierten Graph

PipelineRunner (Klasse):
  run                                 — frischer Lauf, mit Interpreter-Dialog
  modify                              — Modifikation auf vorheriges Blueprint
  _is_interrupted / _get_interrupt_value — LangGraph interrupt() Helpers

Convenience:
  run (modullevel)                    — legacy Wrapper, erzeugt Runner+run()
═══════════════════════════════════════════════════════════════════
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
    punctuation_node,
    inventar_node,
    position_extractor_node,
    text_splitter_node,
    feature_definierer_node,
    platzierer_node,
    assembly_node,
    pocket_child_placer_node,
    blueprint_architect_node,
    blueprint_resolver_node,
    coordinate_validator_node,
    plan_validator_node,
    function_decomposer_node,
    aktions_splitter_node,
    aktions_klassifizierer_node,
    aktions_aggregator_node,
    coder_node,
    code_review_node,
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
    """After interpreter: complete → punctuation → inventar, not complete → loop back."""
    if state.get("is_complete"):
        return "punctuation"
    return "interpreter"


def _is_3step_chain(state: PipelineState) -> bool:
    """Check if this run used the 3-step chain (inventar → feature_definierer → platzierer → assembly)."""
    return bool(state.get("inventar"))


def route_after_coordinate_validator(state: PipelineState) -> str:
    """After coordinate_validator: valid → plan_validator, invalid → retry.

    3-Step Chain runs: route back to feature_definierer (redo features + placement).
    Blueprint Architect runs: route back to blueprint_architect.
    """
    if state.get("coordinate_valid", True):
        return "plan_validator"
    from src.config.loader import get_config
    max_retries = get_config().plan_validator.max_retries
    attempts = state.get("coordinate_validation_attempts", 0)
    if attempts >= max_retries:
        log.warning("route_coordinate_validator", decision="plan_validator",
                    reason="max_retries_exceeded", attempts=attempts)
        return "plan_validator"
    if _is_3step_chain(state):
        log.info("route_coordinate_validator", decision="feature_definierer",
                 attempts=attempts, mode="3step_retry")
        return "feature_definierer"
    log.info("route_coordinate_validator", decision="blueprint_architect",
             attempts=attempts)
    return "blueprint_architect"


def route_after_code_review(state: PipelineState) -> str:
    """After code_review: approved → executor, issues found → coder (max 2 retries)."""
    if state.get("code_review_approved", True):
        return "executor"
    cr_attempts = state.get("code_review_attempts", 0)
    if cr_attempts >= 2:
        log.warning("route_code_review", decision="executor",
                    reason="max_retries_exceeded", attempts=cr_attempts)
        return "executor"
    log.info("route_code_review", decision="coder",
             issues=state.get("code_review_issues", "")[:60])
    return "coder"


def route_after_function_decomposer(state: PipelineState) -> str:
    """After function_decomposer: template mode → executor (skip coder), else → coder."""
    mode = state.get("generation_mode", "llm")
    if mode == "template":
        log.info("route_function_decomposer", decision="executor",
                 reason="all_features_template")
        return "executor"
    log.info("route_function_decomposer", decision="coder", mode=mode)
    return "coder"


def route_after_plan_validator(state: PipelineState) -> str:
    """After plan_validator: valid → function_decomposer, invalid → retry.

    3-Step Chain runs: route back to assembly (structural/parent errors).
    Blueprint Architect runs: route back to blueprint_architect.
    """
    from src.config.loader import get_config
    if state.get("plan_valid", True):
        return "function_decomposer"
    max_retries = get_config().plan_validator.max_retries
    if state.get("plan_validation_attempts", 0) >= max_retries:
        log.warning("route_plan_validator", decision="function_decomposer",
                    reason="max_retries_exceeded",
                    attempts=state.get("plan_validation_attempts"))
        return "function_decomposer"
    if _is_3step_chain(state):
        log.info("route_plan_validator", decision="assembly",
                 issues=state.get("plan_validation_issues", "")[:60],
                 mode="3step_retry")
        return "assembly"
    log.info("route_plan_validator", decision="blueprint_architect",
             issues=state.get("plan_validation_issues", "")[:60])
    return "blueprint_architect"


def build_graph() -> StateGraph:
    """Construct and compile the pipeline graph with checkpointing.

    Architecture (S0 — Modulare Trennung, feature_definierer + platzierer getrennt):

    Fresh requests (Per-Aktion-Kette nach ADR 0003 Stufe 5b):
      entry_router → interpreter → punctuation → inventar (Step A)
        → aktions_splitter → aktions_klassifizierer → text_splitter
        → position_extractor → feature_definierer → aktions_aggregator
        → platzierer → assembly → blueprint_resolver
        → coordinate_validator → plan_validator → ...

    Modify/Error-Loop: blueprint_architect (legacy chain, unchanged).

    Validation failures route back to the originating agent:
      3-Step Chain → feature_definierer (redo features + placement)
      Blueprint Architect (legacy, only entered via error-loop) → blueprint_architect
    """
    checkpointer = MemorySaver()

    graph = StateGraph(PipelineState)

    # --- Nodes ---
    graph.add_node("entry_router", entry_router_node)
    graph.add_node("visioner", visioner_node)
    graph.add_node("interpreter", interpreter_node)
    # Comma-setter — fixes voice input (no commas) before downstream agents
    graph.add_node("punctuation", punctuation_node)
    # 3-Step Blueprint Chain (S0: feature + placement separated)
    graph.add_node("inventar", inventar_node)
    # Per-Aktion-Kette (ADR 0003 Stufe 5b): determ. Splitter → klassifizierer
    # → feature_definierer → aggregator. Ersetzt das verklumpende Inventar
    # Step B durch Pro-Aktion-Mikro-Calls + deterministische Aggregation.
    graph.add_node("aktions_splitter", aktions_splitter_node)
    graph.add_node("aktions_klassifizierer", aktions_klassifizierer_node)
    graph.add_node("position_extractor", position_extractor_node)
    graph.add_node("text_splitter", text_splitter_node)
    graph.add_node("feature_definierer", feature_definierer_node)
    graph.add_node("aktions_aggregator", aktions_aggregator_node)
    graph.add_node("platzierer", platzierer_node)
    graph.add_node("assembly", assembly_node)
    # Optional pre-resolver step: pulls "Bohrung in Tasche"-style features
    # out of the spec and injects them as feature-in-feature children.
    graph.add_node("pocket_child_placer", pocket_child_placer_node)
    # Monolithic fallback for modify/fix
    graph.add_node("blueprint_architect", blueprint_architect_node)
    graph.add_node("blueprint_resolver", blueprint_resolver_node)
    graph.add_node("coordinate_validator", coordinate_validator_node)
    graph.add_node("plan_validator", plan_validator_node)
    graph.add_node("function_decomposer", function_decomposer_node)
    graph.add_node("coder", coder_node)
    graph.add_node("code_review", code_review_node)
    graph.add_node("executor", executor_node)
    graph.add_node("validator", validator_node)
    graph.add_node("error_router", error_router_node)
    graph.add_node("code_fixer", code_fixer_node)

    graph.set_entry_point("entry_router")

    # --- Edges ---

    # Entry router: image → visioner, everything else (incl. modifications) → interpreter
    graph.add_conditional_edges(
        "entry_router",
        route_after_entry_router,
        {
            "interpreter": "interpreter",
            "visioner": "visioner",
        },
    )

    graph.add_edge("visioner", "interpreter")

    # Interpreter loops until spec is complete, then → punctuation → inventar
    graph.add_conditional_edges(
        "interpreter",
        route_after_interpreter,
        {"punctuation": "punctuation", "interpreter": "interpreter"},
    )

    # Punctuation: comma-only pre-processor (voice-input safety net) → inventar
    graph.add_edge("punctuation", "inventar")

    # Per-Aktion-Chain (ADR 0003) — vollstaendiger Fluss:
    #   inventar (Step A) → aktions_splitter (rule)
    #     → aktions_klassifizierer (LLM-Loop, 1 call/Phrase)
    #     → text_splitter (per-Teil Chunks fuer Multi-Part)
    #     → position_extractor (placement vs. feature Labels — feature-
    #       Labels sind im Pro-Aktion-Pfad redundant, placement_sentences
    #       braucht der platzierer weiter)
    #     → feature_definierer (LLM-Loop, define_feature pro Klassifikation)
    #     → aktions_aggregator (rule, baut teil_definitionen[] mit
    #       parent-Aufloesung fuer nested Children)
    #     → platzierer → assembly → resolver
    graph.add_edge("inventar", "aktions_splitter")
    graph.add_edge("aktions_splitter", "aktions_klassifizierer")
    graph.add_edge("aktions_klassifizierer", "text_splitter")
    graph.add_edge("text_splitter", "position_extractor")
    graph.add_edge("position_extractor", "feature_definierer")
    graph.add_edge("feature_definierer", "aktions_aggregator")
    graph.add_edge("aktions_aggregator", "platzierer")
    graph.add_edge("platzierer", "assembly")
    # assembly → pocket_child_placer → blueprint_resolver. The placer
    # is a no-op when the spec doesn't mention "in der Tasche", so this
    # adds zero overhead to the common case.
    graph.add_edge("assembly", "pocket_child_placer")
    graph.add_edge("pocket_child_placer", "blueprint_resolver")

    # Blueprint Architect (modify/fix fallback) → pocket_child_placer →
    # Resolver. Routing through the placer keeps feature-in-feature
    # extraction consistent across both pipelines (3-step + monolithic).
    graph.add_edge("blueprint_architect", "pocket_child_placer")
    graph.add_edge("blueprint_resolver", "coordinate_validator")

    graph.add_conditional_edges(
        "coordinate_validator",
        route_after_coordinate_validator,
        {
            "plan_validator": "plan_validator",
            "blueprint_architect": "blueprint_architect",
            "feature_definierer": "feature_definierer",
        },
    )
    graph.add_conditional_edges(
        "plan_validator",
        route_after_plan_validator,
        {
            "function_decomposer": "function_decomposer",
            "blueprint_architect": "blueprint_architect",
            "assembly": "assembly",
        },
    )

    # Function decomposer → coder (or skip to executor for template mode)
    graph.add_conditional_edges(
        "function_decomposer",
        route_after_function_decomposer,
        {"executor": "executor", "coder": "coder"},
    )

    # Coder → code review → executor
    graph.add_edge("coder", "code_review")
    graph.add_conditional_edges(
        "code_review",
        route_after_code_review,
        {"executor": "executor", "coder": "coder"},
    )
    graph.add_edge("code_fixer", "coder")

    # Executor → validator or error handling
    graph.add_conditional_edges(
        "executor",
        route_after_executor,
        {"validator": "validator", "error_router": "error_router", "end": END},
    )

    # Validator: semantic check — ok → end, bad → retry at agent or coder
    graph.add_conditional_edges(
        "validator",
        route_after_validator,
        {"end": END, "blueprint_architect": "blueprint_architect",
         "feature_definierer": "feature_definierer", "coder": "coder",
         "inventar": "inventar"},
    )

    # Error router: code fix strategies
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
            "is_additive": False,
            # Blueprint + Validation
            "plan_valid": False,
            "plan_validation_issues": "",
            "plan_validation_attempts": 0,
            "coordinate_validation_issues": "",
            "coordinate_valid": True,
            "coordinate_validation_attempts": 0,
            "coordinate_errors_unresolved": False,
            "geometry_state": {},
            "geometry_precheck_report": "",
            "agent_traces": [],
            # 3-Step Blueprint Chain + Per-Aktion-Kette (ADR 0003)
            "inventar": {},
            "position_extrakt": {},
            "teil_definitionen": [],
            "aktions_phrases": [],
            "aktions_klassifikationen": [],
            "aktions_features": [],
            # Code generation
            "code_skeleton": "",
            "generation_mode": "",
            "code_review_issues": "",
            "code_review_approved": True,
            "code_review_attempts": 0,
            "agent_flags": [],
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
            "is_additive": False,
            # Blueprint + Validation
            "plan_valid": False,
            "plan_validation_issues": "",
            "plan_validation_attempts": 0,
            "coordinate_validation_issues": "",
            "coordinate_valid": True,
            "coordinate_validation_attempts": 0,
            "coordinate_errors_unresolved": False,
            "geometry_state": previous_state.get("geometry_state", {}),
            "geometry_precheck_report": "",
            "agent_traces": [],
            # 3-Step Blueprint Chain + Per-Aktion-Kette (ADR 0003)
            "inventar": {},
            "position_extrakt": {},
            "teil_definitionen": [],
            "aktions_phrases": [],
            "aktions_klassifikationen": [],
            "aktions_features": [],
            # Code generation
            "code_skeleton": "",
            "generation_mode": "",
            "code_review_issues": "",
            "code_review_approved": True,
            "code_review_attempts": 0,
            "agent_flags": [],
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
