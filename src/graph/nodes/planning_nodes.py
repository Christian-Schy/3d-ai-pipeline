"""Compatibility facade for planning nodes.

The planning stage is split across smaller modules by responsibility. This
module preserves the historic ``src.graph.nodes.planning_nodes`` import path.
"""
from __future__ import annotations

from ._registry import get_agent, get_raw_response
from .planning_inventory_nodes import (
    inventar_node,
    position_extractor_node,
    text_splitter_node,
)
from .planning_action_nodes import (
    aktions_aggregator_node,
    aktions_klassifizierer_node,
    aktions_splitter_node,
)
from .planning_feature_nodes import (
    feature_definierer_node,
    platzierer_node,
    pocket_child_placer_node,
)
from .planning_assembly_nodes import assembly_node
from .planning_blueprint_nodes import (
    blueprint_architect_node,
    blueprint_resolver_node,
    function_decomposer_node,
)
from .planning_validation_nodes import (
    coordinate_validator_node,
    plan_validator_node,
)

__all__ = [
    "inventar_node",
    "position_extractor_node",
    "text_splitter_node",
    "feature_definierer_node",
    "platzierer_node",
    "assembly_node",
    "pocket_child_placer_node",
    "blueprint_architect_node",
    "blueprint_resolver_node",
    "coordinate_validator_node",
    "plan_validator_node",
    "function_decomposer_node",
    "aktions_splitter_node",
    "aktions_klassifizierer_node",
    "aktions_aggregator_node",
    "get_agent",
    "get_raw_response",
]
