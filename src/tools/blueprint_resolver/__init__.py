"""Blueprint Resolver — semantic → resolved deterministic mapping.

Public API:
    resolve_blueprint(semantic_dict) -> resolved_dict
    BlueprintResolverError           — raised on cycle/validation errors

Package layout:
    core.py        — Public API + topo-sort + BlueprintResolverError
    orientation.py — Step 1: orientation keyword → dim-swap
    face.py        — Step 2: side keyword → CadQuery face selector
    offsets.py     — Step 3: edge_distances / center_offset (face-aware)
    anchor.py      — Step 3b: child-point-on-parent-point placement
    compose.py     — Step 3c + Step 4: combinator + alignment upgrade
    feature.py     — Feature-Resolution glue (per-feature, combines all)
"""

from .core import BlueprintResolverError, resolve_blueprint

__all__ = ["BlueprintResolverError", "resolve_blueprint"]
