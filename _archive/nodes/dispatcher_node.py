"""
src/graph/nodes/dispatcher_node.py — Deterministic agent dispatcher.

Decides which downstream agents are needed based on Feature Tagger output.
No LLM call — pure code logic.

Sits between Feature Tagger and Feature Assigner. Outputs:
  - active_agents: list of agent names that should run
  - agent_flags: list of flags for conditional behavior (e.g., inject_cylinder_rag)
"""

import structlog
from src.graph.state import PipelineState

log = structlog.get_logger()

# Feature types that indicate subtract/modify operations
_SUBTRACT_TYPES = {
    "hole_single", "hole_pattern_circular", "hole_pattern_grid",
    "pocket_rect", "pocket_round", "slot", "groove",
    "fillet", "chamfer", "shell", "taper",
    "arc_cut", "triangle_cut", "custom_shape_cut",
}

# Feature types that indicate add-operation parts
_ADD_PART_TYPES = {
    "extrusion_rect", "extrusion_round", "box", "cylinder",
    "plate", "boss", "rib", "custom_shape_add",
}

# Feature types that need cylinder-specific RAG
_CYLINDER_TYPES = {"cylinder", "extrusion_round", "revolution"}

# Feature types that need shape-cutting RAG
_SHAPE_CUT_TYPES = {"arc_cut", "triangle_cut", "custom_shape_cut", "custom_shape_add"}


def agent_dispatcher_node(state: PipelineState) -> dict:
    """Determine which agents and flags are active for this pipeline run.

    Reads feature_tree from Feature Tagger and decides:
    - Which position assigners need to run
    - Which RAG injections are needed
    - Which future agents to activate

    Returns:
      active_agents: list[str] — agents that should process
      agent_flags: list[str] — flags for conditional behavior
    """
    feature_tree = state.get("feature_tree", {})
    features = feature_tree.get("features_identified", [])
    task_classification = state.get("task_classification", {})

    # Always active
    active_agents = ["feature_assigner", "blueprint_assembler"]
    agent_flags = []

    # Analyze features
    has_subtract = False
    has_add_parts = False
    has_cylinders = False
    has_shape_cuts = False

    for f in features:
        if isinstance(f, dict):
            ftype = f.get("type", "").lower()
        elif isinstance(f, str):
            ftype = f.lower()
        else:
            continue

        # Check feature categories
        if ftype in _SUBTRACT_TYPES or "hole" in ftype or "slot" in ftype or "pocket" in ftype:
            has_subtract = True
        if ftype in _ADD_PART_TYPES:
            has_add_parts = True
        if ftype in _CYLINDER_TYPES or "cylinder" in ftype:
            has_cylinders = True
        if ftype in _SHAPE_CUT_TYPES:
            has_shape_cuts = True

    # Heuristic: if only a base_plate/root and no other parts, check if features
    # suggest add-parts exist (multi-part models usually have >1 feature with parent)
    if len(features) > 1 and not has_add_parts:
        # If there are features beyond root that aren't subtract types,
        # they're likely add-parts
        non_root = [f for f in features
                    if isinstance(f, dict) and f.get("type", "").lower() != "base_plate"]
        for f in non_root:
            ftype = f.get("type", "").lower() if isinstance(f, dict) else ""
            if ftype and ftype not in _SUBTRACT_TYPES:
                has_add_parts = True
                break

    # Conditional agents
    if has_subtract:
        active_agents.append("feature_position_assigner")
    if has_add_parts:
        active_agents.append("part_position_assigner")

    # If neither position assigner is needed (simple single box),
    # still add part_position_assigner as fallback for safety
    if not has_subtract and not has_add_parts:
        # Single root feature, no positioning needed
        log.info("dispatcher_simple_model", features=len(features))

    # Conditional flags
    if has_cylinders:
        agent_flags.append("inject_cylinder_rag")
    if has_shape_cuts:
        agent_flags.append("inject_shape_rag")

    log.info("agent_dispatcher",
             active=active_agents,
             flags=agent_flags,
             features=len(features),
             has_subtract=has_subtract,
             has_add_parts=has_add_parts)

    return {
        "active_agents": active_agents,
        "agent_flags": agent_flags,
    }
