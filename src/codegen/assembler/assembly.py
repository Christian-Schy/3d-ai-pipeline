"""Assembler — sub-assembly orchestration (Phase 3 + Phase 4).

Phase 3 builds the per-part `build_<fid>()` functions that chain a part's
subtract-children and nested add-children. Phase 4 builds the top-level
`assemble()` that fuses the root with all root-level sub-assemblies.

Symbols (intra-package):
    _resolve_part_root           — walk parent chain to the body-owning feature
    _generate_sub_assembly_builds — Phase 3: build_<fid>() functions
    _generate_assemble           — Phase 4: assemble()
"""

from __future__ import annotations

from .transforms import _compute_translate, _emit_face_rotation, _emit_pre_rotation


def _resolve_part_root(fid: str, features: dict) -> str | None:
    """Walk the parent chain upward until we hit a feature that owns a body.

    A "body owner" is either:
      - a root feature (parent is None)
      - an add/union feature (sub-assembly with its own build_ function)

    Subtractive feature parents (e.g. a pocket between a hole and its
    part) are skipped — their cuts are applied to the same body the
    feature-in-feature ultimately attaches to. Returns None if the chain
    is broken (e.g. dangling parent reference).
    """
    visited: set[str] = set()
    current = features.get(fid, {}).get("parent") if isinstance(features.get(fid), dict) else None
    while current is not None:
        if current in visited:
            return None  # cycle — defensive guard
        visited.add(current)
        parent_feat = features.get(current)
        if not isinstance(parent_feat, dict):
            return None
        op = parent_feat.get("operation", "add").lower()
        # Body owners: root (no parent) or any add/union feature
        if parent_feat.get("parent") is None or op in ("add", "union"):
            return current
        # Subtractive ancestor — keep walking up
        current = parent_feat.get("parent")
    return None


def _generate_sub_assembly_builds(
    build_order: list,
    features: dict,
    func_map: dict,
    sub_assemblies: list[dict],
) -> list[str]:
    """Generate build_XYZ() functions that chain sub-assembly operations.

    Handles both subtract-children (holes, slots applied to the part)
    and add-children (nested sub-assemblies translated+unioned onto the part).
    """
    lines = []

    for sa in sub_assemblies:
        sa_fid = sa["fid"]
        sa_prefix = sa_fid.upper().replace("-", "_").replace(" ", "_")
        sa_params = sa["params"]

        # Find ALL children of this sub-assembly part (in build_order sequence)
        subtract_children = []
        add_children = []
        for fid in build_order:
            if fid == sa_fid:
                continue
            feat = features.get(fid, {})
            op = feat.get("operation", "add").lower()
            # Direct add-children (nested sub-assemblies)
            if op in ("add", "union"):
                if feat.get("parent") == sa_fid:
                    add_children.append(fid)
                continue
            # Subtract/modify: include direct children AND descendants
            # whose effective body-owner walks back to this sub-assembly
            # (e.g. hole-in-pocket where pocket.parent == sa_fid).
            if op in ("subtract", "cut", "modify"):
                if feat.get("parent") == sa_fid or _resolve_part_root(fid, features) == sa_fid:
                    subtract_children.append(fid)

        if not subtract_children and not add_children:
            continue  # No build function needed — make_XYZ() suffices

        make_func = func_map.get(sa_fid, f"make_{sa_fid}")
        build_name = f"build_{sa_fid.replace('-', '_').replace(' ', '_')}"

        lines.append(f"def {build_name}() -> cq.Workplane:")
        lines.append(f"    result = {make_func}()")

        # _ref: unmodified body snapshot — used by subtract-children for
        # stable face-bounding-box centers (Cadquery's CenterOfBoundBox shifts
        # after subtractions, which causes drift on later operations).
        # See run 81505d2f for the bug pattern this prevents.
        if subtract_children:
            lines.append("    _ref = result")

        # 1) Apply subtract-children (holes, slots, modifiers)
        for child_fid in subtract_children:
            child_func = func_map.get(child_fid)
            if child_func:
                lines.append(f"    result = {child_func}(result, _ref)")

        # 2) Nested add-children (sub-assemblies on this part)
        for child_fid in add_children:
            child_feat = features.get(child_fid, {})
            child_params = child_feat.get("params", {})
            child_placement = child_feat.get("placement") or {}
            child_prefix = child_fid.upper().replace("-", "_").replace(" ", "_")
            clean_child = child_fid.replace("-", "_").replace(" ", "_")

            # Does this nested SA itself have children? → use build_ or make_
            nested_has_children = any(
                fid2 != child_fid
                and features.get(fid2, {}).get("parent") == child_fid
                for fid2 in build_order
            )
            if nested_has_children:
                child_build = f"build_{clean_child}"
            else:
                child_build = func_map.get(child_fid, f"make_{clean_child}")

            face = child_placement.get("face", ">Z")
            translate_code = _compute_translate(
                face, sa_prefix, sa_params, child_prefix, child_params
            )

            lines.append(f"    {clean_child} = {child_build}()")
            pre_rot = child_placement.get("pre_rotation")
            lines.extend(_emit_pre_rotation(clean_child, child_prefix, child_params, pre_rot))
            child_angle = float(child_placement.get("angle_deg", 0) or 0)
            if child_angle != 0.0:
                lines.extend(_emit_face_rotation(clean_child, child_prefix, child_params, face, child_angle))
            lines.append(f"    {clean_child} = {clean_child}.translate({translate_code})")
            lines.append(f"    result = result.union({clean_child}).clean()")

        lines.append("    return result")
        lines.append("")

    return lines


def _generate_assemble(
    root_id: str,
    build_order: list,
    features: dict,
    func_map: dict,
    sub_assemblies: list[dict],
) -> list[str]:
    """Generate the assemble() function."""
    lines = []
    root_func = func_map.get(root_id, f"make_{root_id}")
    root_params = features.get(root_id, {}).get("params", {})
    root_prefix = root_id.upper().replace("-", "_").replace(" ", "_")

    lines.append("def assemble() -> cq.Workplane:")
    lines.append(f"    result = {root_func}()")
    lines.append("")

    # Apply base subtracts (features directly on root, before any union)
    sa_fids = {sa["fid"] for sa in sub_assemblies}
    base_subtract_fids = []
    for fid in build_order:
        if fid == root_id or fid in sa_fids:
            continue
        feat = features.get(fid, {})
        op = feat.get("operation", "add").lower()
        if op not in ("subtract", "cut", "modify"):
            continue
        # Direct child of root, OR feature-in-feature whose effective
        # body-owner walks back to root (e.g. hole-in-pocket-on-root).
        if feat.get("parent") == root_id or _resolve_part_root(fid, features) == root_id:
            base_subtract_fids.append(fid)

    # _ref: unmodified body snapshot for stable face origins (see
    # _generate_sub_assembly_builds comment on the same pattern).
    if base_subtract_fids:
        lines.append("    _ref = result")
    for fid in base_subtract_fids:
        func = func_map.get(fid)
        if func:
            lines.append(f"    result = {func}(result, _ref)")

    # Sub-assemblies: build, translate, union
    # Process only root-level sub-assemblies here; nested ones are handled
    # inside their parent's build_ function
    for sa in sub_assemblies:
        sa_fid = sa["fid"]
        sa_parent = sa["parent"]

        # Skip nested sub-assemblies (their parent is not root)
        if sa_parent != root_id:
            continue

        placement = sa["placement"]
        sa_params = sa["params"]
        sa_prefix = sa_fid.upper().replace("-", "_").replace(" ", "_")

        # Check if this sa has any children (subtract OR add)
        has_children = any(
            fid != sa_fid
            and features.get(fid, {}).get("parent") == sa_fid
            for fid in build_order
        )
        if has_children:
            build_func = f"build_{sa_fid.replace('-', '_').replace(' ', '_')}"
        else:
            build_func = func_map.get(sa_fid, f"make_{sa_fid}")

        clean_fid = sa_fid.replace("-", "_").replace(" ", "_")
        lines.append("")
        lines.append(f"    # --- Sub-assembly: {sa_fid} ---")
        lines.append(f"    {clean_fid} = {build_func}()")

        pre_rot = placement.get("pre_rotation")
        lines.extend(_emit_pre_rotation(clean_fid, sa_prefix, sa_params, pre_rot))

        # Translate based on face — use PARENT dimensions, not always root
        face = placement.get("face", ">Z")
        sa_angle = float(placement.get("angle_deg", 0) or 0)
        if sa_angle != 0.0:
            lines.extend(_emit_face_rotation(clean_fid, sa_prefix, sa_params, face, sa_angle))
        translate_code = _compute_translate(
            face, root_prefix, root_params, sa_prefix, sa_params
        )
        lines.append(f"    {clean_fid} = {clean_fid}.translate({translate_code})")
        lines.append(f"    result = result.union({clean_fid}).clean()")

    lines.append("")
    lines.append("    return result")

    return lines
