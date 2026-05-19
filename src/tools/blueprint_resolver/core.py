"""
src/tools/blueprint_resolver.py — Converts Semantic Blueprint → Resolved Blueprint.

100% deterministic, no LLM. Handles:
  1. Orientation resolution: "hochkant" → dimension swap in params
  2. Face calculation: "rechts" → ">X" face selector
  3. Offset calculation: anchor / edge_distances / center_offset / alignment
     → numeric offset_x / offset_y (face-aware)
  4. Angle preservation: angle_deg passed through to resolved placement
  5. Anchor resolution: child-point-on-parent-point placement (corners, edges,
     centers) with optional pre_rotation (3D) passed through to the assembler

This is the ONLY place where dimension swaps and offset math happen.
The AI never computes these values.

═══════════════════════════════════════════════════════════════════
STRUKTUR (bei Aenderungen pflegen! Siehe CLAUDE.md)
═══════════════════════════════════════════════════════════════════
Public API:
  resolve_blueprint(semantic)      — semantic dict → resolved dict;
                                     idempotent; legacy pass-through;
                                     topo-sortiert dann delegiert pro
                                     Feature an _resolve_feature aus
                                     .feature (mit _fallback_resolve im
                                     Exception-Fall)

Topo-Sort:
  _topo_sort_features              — Kahn's Algo auf parent-Kanten,
                                     Original-Order als Tiebreaker,
                                     Cycle-Detection → BlueprintResolverError
  BlueprintResolverError           — Cycle/Validation-Fehler im Resolver

Sub-Module (kein direkter Code in core.py):
  .orientation — Step 1: orientation keyword → dim-swap
  .face        — Step 2: side keyword → CadQuery face selector
  .offsets     — Step 3: face-aware edge/center offset math
  .anchor      — Step 3b: child-point-on-parent-point placement
  .compose     — Step 3c + Step 4: _compute_offsets + alignment upgrade
  .feature     — Feature-Resolution (_resolve_feature {,_in_feature,
                 _with_part_frame, _fallback_resolve}, _is_feature_parent,
                 _FEATURE_PARENT_TYPES)
═══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import structlog

from .feature import _fallback_resolve, _resolve_feature

log = structlog.get_logger()


# ═══════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════

def resolve_blueprint(semantic: dict) -> dict:
    """Convert a semantic blueprint dict to a resolved blueprint dict.

    Input:  semantic blueprint with orientation + position (side/alignment/edge_distances)
    Output: resolved blueprint with placement (face/offset_x/offset_y) and swapped params

    If the blueprint is already resolved (has 'placement'), returns it unchanged.
    """
    features = semantic.get("features", {})
    if not features:
        return semantic

    # Check if ANY feature has semantic fields (orientation or position.side).
    # If none do AND all have placement → true legacy, pass through.
    # If mixed (fix-mode: AI returned placement but lost orientation) → resolve anyway.
    has_any_semantic = False
    has_any_placement = False
    for feat in features.values():
        if not isinstance(feat, dict):
            continue
        if "orientation" in feat:
            has_any_semantic = True
        pos = feat.get("position", {})
        if isinstance(pos, dict) and "side" in pos:
            has_any_semantic = True
        if "placement" in feat and feat.get("placement") is not None:
            has_any_placement = True

    if not has_any_semantic and has_any_placement:
        # True legacy blueprint — all features have placement, none have semantic fields
        return semantic

    # Topo-sort the build_order so parents resolve before children.
    # Required for feature-in-feature placement (hole inside pocket) where
    # the child's offsets depend on the parent's resolved placement.
    original_order = semantic.get("build_order", []) or list(features.keys())
    sorted_order = _topo_sort_features(original_order, features)

    resolved_features = {}
    for fid in sorted_order:
        feat = features.get(fid)
        if not isinstance(feat, dict):
            if feat is not None:
                resolved_features[fid] = feat
            continue
        try:
            # Pass already-resolved features so feature-parent lookups succeed.
            resolved_features[fid] = _resolve_feature(
                fid, feat, features, resolved_features
            )
        except Exception as e:
            log.warning("resolver_feature_error", feature=fid, error=str(e))
            # Fallback: convert as-is with defaults
            resolved_features[fid] = _fallback_resolve(fid, feat)

    return {
        "description": semantic.get("description", ""),
        "build_order": sorted_order,
        "features": resolved_features,
    }


def _topo_sort_features(original_order: list[str], features: dict) -> list[str]:
    """Sort feature IDs so every parent comes before its children.

    Uses Kahn's algorithm with the original LLM-provided order as the
    tie-breaker, so the result is stable when no parent constraints force
    a reorder. Features whose `parent` references something not in
    `features` are treated as roots (in-degree 0) — no silent loss.

    Raises BlueprintResolverError on cycle detection so the pipeline
    surfaces the problem rather than producing wrong geometry.
    """
    feat_ids = list(features.keys())
    # Preserve original_order ordering for IDs present in features;
    # append any feature missing from original_order at the end.
    seen = set()
    primary: list[str] = []
    for fid in original_order:
        if fid in features and fid not in seen:
            primary.append(fid)
            seen.add(fid)
    for fid in feat_ids:
        if fid not in seen:
            primary.append(fid)
            seen.add(fid)

    # Compute in-degree (each feature has at most one parent in our schema).
    in_degree: dict[str, int] = {fid: 0 for fid in primary}
    children: dict[str, list[str]] = {fid: [] for fid in primary}
    for fid in primary:
        feat = features.get(fid, {})
        parent = feat.get("parent") if isinstance(feat, dict) else None
        if parent and parent in in_degree:
            in_degree[fid] = 1
            children[parent].append(fid)

    # Tie-break by primary order: pop the first ready node in primary order.
    primary_index = {fid: i for i, fid in enumerate(primary)}
    ready = sorted(
        [fid for fid, deg in in_degree.items() if deg == 0],
        key=lambda f: primary_index[f],
    )
    sorted_out: list[str] = []
    while ready:
        fid = ready.pop(0)
        sorted_out.append(fid)
        for child in children.get(fid, []):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                # Insert into ready while preserving primary-order tiebreak.
                idx = 0
                ci = primary_index[child]
                while idx < len(ready) and primary_index[ready[idx]] < ci:
                    idx += 1
                ready.insert(idx, child)

    if len(sorted_out) != len(primary):
        cycle = [fid for fid in primary if fid not in sorted_out]
        raise BlueprintResolverError(
            f"Cycle in feature parent graph: {cycle}"
        )
    return sorted_out


class BlueprintResolverError(Exception):
    """Raised when the resolver cannot produce a valid resolved blueprint."""


# All resolver steps now live in sub-modules:
#   Step 1   Orientation  → .orientation
#   Step 2   Face         → .face
#   Step 3   Offsets      → .offsets
#   Step 3b  Anchor       → .anchor
#   Step 3c  Compose      → .compose  (also Step 4 alignment upgrade)
#   Feature  Resolution   → .feature  (uses all of the above)
# core.py keeps only the public API (resolve_blueprint), the topo-sort,
# and BlueprintResolverError. .feature is the only direct import — it
# transitively pulls in the rest.


