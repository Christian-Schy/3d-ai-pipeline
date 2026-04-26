"""
src/graph/state.py — The single source of truth for the entire pipeline.

Every node reads from this state and writes back to it.
No node talks directly to another node — all communication goes through here.

Why TypedDict and not a Dataclass?
  LangGraph works with TypedDict natively. It knows how to merge partial
  state updates: a node only needs to return the fields it changed,
  not the entire state object. With a Dataclass we'd have to return
  everything every time.

═══════════════════════════════════════════════════════════════════
STRUKTUR (bei Aenderungen pflegen! Siehe CLAUDE.md)
═══════════════════════════════════════════════════════════════════
PipelineState-Felder, gruppiert nach Producer-Node:

  Input (vor Graph-Start gesetzt):
    description, raw_input, image_path

  Interpreter:
    messages, specification, is_complete, interpreter_features

  3-Step Blueprint Chain (Phase A):
    inventar, teil_texte, position_extrakt, teil_definitionen

  Planner / Blueprint (semantic + resolved):
    blueprint, previous_blueprint

  Coder / Code-Generation:
    code, previous_code, code_skeleton, generation_mode

  Executor / STL:
    stl_path, previous_stl_path, execution_error, geometry_state,
    geometry_precheck_report

  Validator (semantisch):
    validation_error, validator_feedback, validator_stats,
    semantic_attempts

  Plan-Validator (LLM, Blueprint-Struktur):
    plan_valid, plan_validation_issues, plan_validation_attempts

  Coordinate-Validator (deterministisch, Geometrie):
    coordinate_valid, coordinate_validation_issues,
    coordinate_validation_attempts

  Code-Review:
    code_review_issues, code_review_approved, code_review_attempts

  Error-Loop / Fixer:
    attempts, phase, fix_plan, previous_validation_error

  Modification / Editing:
    modification, change_description, is_additive, changed_features

  Feedback / Training:
    feedback, agent_traces, agent_flags
═══════════════════════════════════════════════════════════════════
"""

import operator
from typing import Annotated, Any
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class PipelineState(TypedDict):
    """The data object that flows through the entire graph.

    Fields are grouped by which agent writes them.
    A field is None until the responsible agent fills it in.
    """

    # --- Input (set before the graph starts) ---
    description: str
    """The raw user input: 'Make a 30mm cube with a hole in the top'"""

    raw_input: str
    """The original user input, never overwritten. Preserved for session logging
    even after description is replaced with the canonical blueprint label."""

    # --- Interpreter ---
    messages: Annotated[list[Any], add_messages]
    """Dialog history between Interpreter and user.
    
    Annotated with add_messages: LangGraph automatically appends new
    messages instead of replacing the whole list. That way we never
    lose dialog history by accident.
    """
    specification: str
    """The complete, unambiguous model specification after Interpreter is done.
    Example: 'Rectangular box 30x20x10mm, single M3 hole centered on top face,
              hole depth 8mm, 1mm chamfer on all top edges.'
    """
    is_complete: bool
    """True when Interpreter is satisfied that the spec is complete enough
    for Planner to work with. False = still asking clarifying questions."""

    # --- Planner ---
    blueprint: dict[str, Any]
    """The CSG-Tree build plan as a structured dict.
    
    Planner writes this. Coder reads it.
    In Stufe 1 this is just a dict — the CSG-Tree schema comes in Stufe 5.
    """

    # --- Coder ---
    code: str
    """The generated CadQuery Python code."""

    # --- Executor / Validator ---
    stl_path: str
    """Absolute path to the generated STL file after successful execution."""

    execution_error: str
    """Error message from the sandbox if execution failed. Empty string = no error."""

    validation_error: str
    """Error message from STLValidator if geometry is broken. Empty string = no error."""

    # --- Error loop ---
    attempts: int
    """How many times we've tried to fix errors so far.
    Starts at 0. The error loop increments this each cycle."""

    phase: int
    """Which error-repair phase we're in (1, 2, or 3).
    
    Phase 1 — Coder fixes its own code based on the error message.
    Phase 2 — Planner rewrites the Blueprint from scratch.
    Phase 3 — Give up and report failure to the user.
    (Defined in Stufe 3 — for now this field just exists.)
    """


    # --- Validator (semantic check after successful STL) ---
    semantic_attempts: int
    """How many times the Validator said semantically wrong and sent
    the Planner back to the drawing board. Max 2 before we give up."""

    validator_feedback: str
    """The Validators explanation of what is wrong semantically.
    Passed to the Planner so it can correct the Blueprint.
    Example: Blueprint specifies a hole on the top face but the generated
             model has no hole — the cutBlind operation is missing."""

    # --- CodeFixer (Phase 2 of error loop) ---
    fix_plan: str
    """CodeFixerAgents analysis of repeated failures.
    Passed to Coder as additional context for the next attempt.
    Example: The error repeats because cutBlind() is called before the
             workplane is positioned on the correct face."""

    # --- Feedback & training (used in Stufe 7+) ---
    feedback: str
    """User feedback after seeing the result: 'good', 'bad', or '' (none yet)."""

    # --- Iterative editing (Stufe 6) ---
    modification: str
    """If the user wants to change an existing model:
    'Make the holes 2mm bigger'
    Empty string = this is a fresh request, not a modification."""

    previous_blueprint: dict
    """The last successfully validated Blueprint.
    Preserved after a successful run so Planner can patch it on modification.
    Empty dict = no previous run yet."""

    previous_code: str
    """The last successfully validated CadQuery code.
    Preserved so the Coder can use it as a starting point for modifications
    instead of regenerating from scratch — prevents slot/feature drift."""

    previous_stl_path: str
    """Path to the last successfully generated STL.
    Preserved so the user can still access the previous version
    while a modification is being processed."""

    validator_stats: dict
    """Stats dict from the last successful ValidatorAgent.check() call.
    Contains: size_mm (sorted [x,y,z] extents), volume_mm3, triangles, watertight.
    Written by validator_node on success. Read by executor_node to detect volume
    changes on modification runs (volume delta check). Also consumed by the 3D viewer
    and session history to display model dimensions."""

    change_description: str
    """The precise change to apply to the existing Blueprint.
    Written by entry_router_node after ModificationInterpreter classifies input.
    Empty string = fresh request, not a modification."""

    image_path: str
    """Optional path to an uploaded image or sketch.
    If set, VisionerAgent runs before the Interpreter and produces
    a partial specification that the Interpreter then completes."""

    is_additive: bool
    """True when the modification adds new geometry (e.g. adds a boss, fillet, extra hole).
    False = subtractive or reshape. Used by validator to expect a volume increase."""

    # --- Function Decomposer ---
    code_skeleton: str
    """Python skeleton generated by FunctionDecomposer.
    One stub function per feature + assemble(). Coder fills in the function bodies.
    Empty string = no skeleton available (legacy CSG-Tree pipeline or single-feature model)."""

    generation_mode: str
    """How code was generated by FunctionDecomposer:
    'template' — all features handled by deterministic templates, Coder skipped.
    'mixed'    — standard features filled by templates, complex stubs need Coder.
    'llm'      — all features need LLM code generation (skeleton only).
    Empty string = legacy flow (FunctionDecomposer didn't run)."""

    # --- Coordinate Validator ---
    coordinate_validation_issues: str
    """Issues found by the rule-based CoordinateValidator.
    Non-empty = Planner sent back to fix geometry. Empty = all checks passed."""

    coordinate_valid: bool
    """True when CoordinateValidator found no ERROR-severity issues."""

    coordinate_validation_attempts: int
    """How many times CoordinateValidator has rejected the blueprint (this run).
    Own counter — separate from plan_validation_attempts to prevent infinite loops."""

    # --- Phase 2 — Code Review Agent ---
    code_review_issues: str
    """Issues found by the Code Review Agent (static analysis of generated code).
    Non-empty = Coder sent back to fix specific functions. Empty = approved."""

    code_review_approved: bool
    """True when Code Review Agent found no ERROR-severity issues."""

    code_review_attempts: int
    """How many code_review → coder cycles have run. Resets each pipeline run."""

    # --- Plan-Validator ---
    plan_valid: bool
    """True when Plan-Validator approved the blueprint. False = rejected."""

    plan_validation_issues: str
    """Issues found by Plan-Validator. Passed back to Planner for correction.
    Empty string = no issues."""

    plan_validation_attempts: int
    """How many times Plan-Validator has rejected the current blueprint (this run).
    Resets to 0 at the start of each pipeline run. Max = config.plan_validator.max_retries."""

    # --- Geometry-State (V4) ---
    geometry_state: dict
    """BBox, volume, and face info extracted after each successful build().
    Written by executor_node. Read by PromptAssembler when requires_current_geometry=True."""

    geometry_precheck_report: str
    """Deterministic geometry pre-check report generated after each successful build.
    Written by executor_node. Passed to ValidatorAgent as trusted context to prevent
    hallucination. Contains volume delta, feature presence analysis, and BBox checks."""

    # --- Interpreter Reasoning (#20) ---
    interpreter_features: list
    """Feature list extracted by InterpreterAgent's geometric reasoning step.
    Each entry is a string: "feature_id: Type Dimensions, Parent=X, Face=Y, Offset=(a,b)".
    Written by interpreter_node. Read by feature_tagger_node as a starting hint
    to avoid redundant feature identification work.
    Empty list = no interpreter pre-analysis available."""

    # --- Modification Guard (#18) ---
    changed_features: list
    """Feature IDs that changed in a modification request.
    Written by modification_interpreter_node from LLM output.
    Empty list = all features changed / fresh request.
    Used by CoderAgent._fill_skeleton() to only regenerate modified functions."""

    # --- Repeated error detection ---
    previous_validation_error: str
    """Validation error from the previous attempt. Used by error_router_node to detect
    when the same geometry error (e.g. 'not watertight') repeats across attempts,
    so a different fix strategy can be suggested."""

    # --- Feature-specific RAG flags ---
    agent_flags: list
    """Conditional behavior flags for feature-specific RAG injection.
    Examples: 'inject_cylinder_rag', 'inject_shape_rag'.
    Read by Coder for feature-specific RAG injection."""

    # --- 3-Step Blueprint Chain (Phase A) ---
    inventar: dict
    """Parts inventory from InventarAgent (Step 1).
    Contains: teil_count, teile[{id, type, beschreibung, raw_params}], aktionen.
    Empty dict = inventar not yet run or single-part shortcut."""

    teil_texte: dict
    """Per-part focused text from TextSplitterAgent (Step 1a).
    Maps teil_id → text segment extracted from the full spec.
    Each agent call for that part uses this text instead of the full spec,
    so it doesn't get confused by other parts' descriptions.
    Empty dict = splitter not yet run or single-part (no splitting needed)."""

    position_extrakt: dict
    """Per-teil position descriptions from PositionExtractorAgent (Step 1b).
    Contains: positionen[{teil_id, parent_hint, beschreibung}].
    Empty dict = extractor not run (single-part or not yet executed).
    Feeds PositionNormalizer with pre-digested text instead of full spec."""

    teil_definitionen: list
    """Per-part feature definitions from TeilDefiniererAgent (Step 2).
    Each entry: {id, type, params, orientation, features[...]}.
    Empty list = teil_definierer not yet run."""

    # --- Agent Traces (Aufgabe 9) ---
    agent_traces: Annotated[list, operator.add]
    """Per-agent input/output/timing log for training data collection.

    Each node appends one trace entry by returning {"agent_traces": [new_trace]}.
    Annotated[list, operator.add] tells LangGraph to accumulate entries instead
    of replacing the list on each state update.
    """
