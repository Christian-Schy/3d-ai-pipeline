"""Blueprint Resolver — semantic → resolved deterministic mapping.

Public API:
    resolve_blueprint(semantic_dict) -> resolved_dict
    BlueprintResolverError           — raised on cycle/validation errors

Package layout (in progress — see CLAUDE.md "Refactor-Pass"):
    core.py        — Public API + topo-sort + feature resolution glue
    orientation.py — Step 1: orientation keyword → dim-swap
    face.py        — Step 2: side keyword → CadQuery face selector

Remaining sections still in core.py (extracted in follow-up sessions):
    Step 3   — Offsets (edge_distances / pocket_edge_distances / center_offset)
    Step 3b  — Anchor (child-point-on-parent-point)
    Step 3c  — Compose (_compute_offsets, alignment upgrade)
    Feature  — _resolve_feature / _resolve_feature_in_feature
"""

from .core import resolve_blueprint, BlueprintResolverError

__all__ = ["resolve_blueprint", "BlueprintResolverError"]
