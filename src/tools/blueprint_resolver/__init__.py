"""Blueprint Resolver — semantic → resolved deterministic mapping.

Public API:
    resolve_blueprint(semantic_dict) -> resolved_dict
    BlueprintResolverError           — raised on cycle/validation errors

Package layout (in progress — see CLAUDE.md "Refactor-Pass"):
    core.py        — Public API + topo-sort + feature resolution glue
    orientation.py — Step 1: orientation keyword → dim-swap
    face.py        — Step 2: side keyword → CadQuery face selector
    offsets.py     — Step 3: edge_distances / center_offset (face-aware)
    anchor.py      — Step 3b: child-point-on-parent-point placement
    compose.py     — Step 3c + Step 4: combinator + alignment upgrade

Remaining sections still in core.py (extracted in follow-up sessions):
    Feature  — _resolve_feature / _resolve_feature_in_feature
"""

from .core import resolve_blueprint, BlueprintResolverError

__all__ = ["resolve_blueprint", "BlueprintResolverError"]
