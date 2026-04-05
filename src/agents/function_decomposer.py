"""
src/agents/function_decomposer.py — Generates a Python skeleton from a Feature Tree.

Phase 1 new node. Sits between Plan-Validator and Coder.

Rule-based (no LLM). Takes the Feature Tree blueprint and generates a
Python skeleton with one function per feature plus an assemble() function.
The Coder receives this skeleton and fills in each function body.

Design decision (from restructuring doc §7):
  "Function Decomposer: regelbasiert (Template-basiert), LLM nur als Fallback"

Why a skeleton:
  - Coder gets clear, isolated tasks instead of "write everything at once"
  - Each function can be fixed individually on error
  - Modifications only touch the affected function
  - The decomposer needs no CadQuery knowledge — just structure
"""

import re
import structlog
from src.graph.state import PipelineState
from src.graph.feature_tree import FeatureTree, FeatureEntry
from src.codegen.assembler import generate_code as generate_template_code
from src.codegen.feature_classifier import classify_blueprint

log = structlog.get_logger()


# ------------------------------------------------------------------
# NearestToPointSelector computation
# ------------------------------------------------------------------

def _compute_offsets_for_alignment(
    alignment: str, pw: float, pl: float, fw: float, fl: float,
    explicit_ox: float | None = None, explicit_oy: float | None = None,
) -> tuple[float, float]:
    """Compute (offset_x, offset_y) from alignment + parent/feature dims."""
    ox = float(explicit_ox) if explicit_ox is not None else 0.0
    oy = float(explicit_oy) if explicit_oy is not None else 0.0

    if explicit_ox is None and alignment:
        if "right" in alignment and pw and fw:
            ox = pw / 2 - fw / 2
        elif "left" in alignment and pw and fw:
            ox = -(pw / 2 - fw / 2)
    if explicit_oy is None and alignment:
        if "top" in alignment and pl and fl:
            oy = pl / 2 - fl / 2
        elif "bottom" in alignment and pl and fl:
            oy = -(pl / 2 - fl / 2)
    return (ox, oy)


def _compute_feature_positions(ft: FeatureTree) -> dict[str, dict]:
    """Compute absolute center and half-extents of all additive features.

    Used to generate NearestToPointSelector constants for features after union.
    Only computes for root + add features (subtract features don't change shape).

    Returns: {feature_id: {"center": (cx,cy,cz), "half": (hx,hy,hz)}}
    """
    pos: dict[str, dict] = {}

    for fid in ft.build_order:
        feature = ft.features.get(fid)
        if not feature:
            continue
        params = feature.params or {}

        if feature.parent is None:
            w = float(params.get("x") or params.get("diameter") or 0)
            l = float(params.get("y") or params.get("diameter") or 0)
            h = float(params.get("z") or params.get("height") or 0)
            pos[fid] = {"center": (0.0, 0.0, h / 2), "half": (w / 2, l / 2, h / 2)}
            continue

        if feature.operation != "add":
            continue

        parent_pos = pos.get(feature.parent)
        if not parent_pos:
            continue

        pl = feature.placement
        if not pl:
            continue

        face = pl.face or ">Z"
        pcx, pcy, pcz = parent_pos["center"]
        phx, phy, phz = parent_pos["half"]

        fw = float(params.get("x") or 0)
        fl = float(params.get("y") or 0)
        fh = float(params.get("z") or params.get("height") or 0)

        parent_feat = ft.features.get(feature.parent)
        pp = (parent_feat.params or {}) if parent_feat else {}
        pw = float(pp.get("x") or 0)
        py_dim = float(pp.get("y") or 0)

        ox, oy = _compute_offsets_for_alignment(
            pl.alignment or "", pw, py_dim, fw, fl,
            pl.offset_x, pl.offset_y,
        )

        if face == ">Z":
            pos[fid] = {
                "center": (pcx + ox, pcy + oy, pcz + phz + fh / 2),
                "half": (fw / 2, fl / 2, fh / 2),
            }
        elif face == "<Z":
            pos[fid] = {
                "center": (pcx + ox, pcy + oy, pcz - phz - fh / 2),
                "half": (fw / 2, fl / 2, fh / 2),
            }
        elif face == ">X":
            pos[fid] = {
                "center": (pcx + phx + fh / 2, pcy + ox, pcz + oy),
                "half": (fh / 2, fw / 2, fl / 2),
            }
        elif face == "<X":
            pos[fid] = {
                "center": (pcx - phx - fh / 2, pcy + ox, pcz + oy),
                "half": (fh / 2, fw / 2, fl / 2),
            }
        elif face == ">Y":
            pos[fid] = {
                "center": (pcx + ox, pcy + phy + fh / 2, pcz + oy),
                "half": (fw / 2, fh / 2, fl / 2),
            }
        elif face == "<Y":
            pos[fid] = {
                "center": (pcx + ox, pcy - phy - fh / 2, pcz + oy),
                "half": (fw / 2, fh / 2, fl / 2),
            }
        else:
            pos[fid] = {
                "center": (pcx, pcy, pcz),
                "half": (fw / 2, fl / 2, fh / 2),
            }

    return pos


def _face_center_point(
    parent_pos: dict, face: str
) -> tuple[float, float, float] | None:
    """Compute the center point of a specific face on the parent feature."""
    if not parent_pos:
        return None
    cx, cy, cz = parent_pos["center"]
    hx, hy, hz = parent_pos["half"]
    return {
        ">Z": (cx, cy, cz + hz),
        "<Z": (cx, cy, cz - hz),
        ">X": (cx + hx, cy, cz),
        "<X": (cx - hx, cy, cz),
        ">Y": (cx, cy + hy, cz),
        "<Y": (cx, cy - hy, cz),
    }.get(face)


def _features_needing_ntp(ft: FeatureTree) -> set[str]:
    """Return feature IDs that need NearestToPointSelector (after first union)."""
    first_union_idx = None
    for i, fid in enumerate(ft.build_order):
        f = ft.features.get(fid)
        if f and f.parent is not None and f.operation == "add":
            first_union_idx = i
            break
    if first_union_idx is None:
        return set()
    return {fid for i, fid in enumerate(ft.build_order) if i > first_union_idx}


# ------------------------------------------------------------------
# Function naming
# ------------------------------------------------------------------

def _function_name(feature: FeatureEntry) -> str:
    """Derive a Python function name from feature id and operation."""
    fid = feature.id.replace("-", "_").replace(" ", "_").lower()
    ftype = feature.type.lower()

    if feature.parent is None:
        return f"make_{fid}"

    if feature.operation == "subtract":
        if any(kw in ftype for kw in ("hole", "drill", "bore", "cbore", "csk")):
            return f"drill_{fid}"
        elif any(kw in ftype for kw in ("slot", "groove", "pocket", "cut")):
            return f"cut_{fid}"
        elif "corner" in ftype:
            return f"cut_{fid}"
        elif "text" in ftype:
            return f"engrave_{fid}"
        else:
            return f"subtract_{fid}"
    else:
        if any(kw in ftype for kw in ("fillet", "chamfer")):
            return f"apply_{fid}"
        elif "shell" in ftype:
            return f"hollow_{fid}"
        elif "text" in ftype:
            return f"emboss_{fid}"
        else:
            return f"add_{fid}"


# ------------------------------------------------------------------
# Docstring builder
# ------------------------------------------------------------------

def _detect_slot_axis(feature: FeatureEntry) -> str:
    """Detect slot/groove axis direction from feature ID, notes, or placement notes.

    Returns 'X' or 'Y'. Defaults to 'Y' if ambiguous (most common case).
    """
    # Check feature ID: "pocket_y_axis", "nut_y_axis", "groove_x" etc.
    fid_lower = feature.id.lower()
    if "x_axis" in fid_lower or "_x" in fid_lower or "along_x" in fid_lower:
        return "X"
    if "y_axis" in fid_lower or "_y" in fid_lower or "along_y" in fid_lower:
        return "Y"

    # Check placement notes: "Nut entlang Y", "slot along X"
    notes = ""
    if feature.placement and feature.placement.notes:
        notes = feature.placement.notes.lower()
    if feature.notes:
        notes += " " + feature.notes.lower()

    if "entlang x" in notes or "along x" in notes:
        return "X"
    if "entlang y" in notes or "along y" in notes:
        return "Y"

    # Default: Y axis (most common for "Nut entlang")
    return "Y"


def _make_docstring(feature: FeatureEntry, *, needs_ntp: bool = False) -> str:
    """Build an informative docstring from feature metadata."""
    lines = [f'    """']
    lines.append(f"    Type: {feature.type}")

    if feature.params:
        param_str = ", ".join(
            f"{k}={v}" for k, v in feature.params.items()
        )
        lines.append(f"    Params: {param_str}")

    if feature.parent:
        lines.append(f"    Parent: {feature.parent}")

    prefix = feature.id.upper().replace("-", "_").replace(" ", "_")

    if feature.placement:
        pl = feature.placement
        parts = [f"face={pl.face}"]
        if pl.alignment:
            parts.append(f"alignment={pl.alignment}")
        if pl.z_position:
            parts.append(f"z={pl.z_position}")
        parts.append(f"pos={pl.position}")
        lines.append(f"    Placement: {', '.join(parts)}")
        # Hint: tell Coder which pre-computed constants to use for offsets
        lines.append(f"    ★ Use {prefix}_OFFSET_X / {prefix}_OFFSET_Y for .center() call")
    elif feature.position:
        lines.append(f"    Position: {feature.position}")

    lines.append(f"    Operation: {feature.operation}")

    # Slot/groove axis hint
    if feature.type.lower() in ("slot", "groove"):
        slot_axis = _detect_slot_axis(feature)
        if slot_axis == "Y":
            lines.append(f"    ★ NUT entlang Y-Achse → .rect({prefix}_WIDTH, {prefix}_LENGTH).cutBlind(-{prefix}_DEPTH)")
        else:
            lines.append(f"    ★ NUT entlang X-Achse → .rect({prefix}_LENGTH, {prefix}_WIDTH).cutBlind(-{prefix}_DEPTH)")
        lines.append(f"    ★ KEIN slot2D! rect() macht rechteckige Nut ohne Rundungen")

    if needs_ntp:
        lines.append(f"    ★★ AFTER UNION — use NearestToPointSelector for face selection:")
        lines.append(f"    body.faces(NearestToPointSelector({prefix}_SELECTOR_POINT))")
        lines.append(f"    .workplane(centerOption='CenterOfBoundBox')")
        lines.append(f"    Do NOT use body.faces(\"{feature.placement.face if feature.placement else '>Z'}\") — it picks the WRONG face after union!")

    if feature.notes:
        lines.append(f"    Notes: {feature.notes}")

    lines.append('    """')
    return "\n".join(lines)


# ------------------------------------------------------------------
# Parameter constant generator
# ------------------------------------------------------------------

def _generate_param_constants(ft: FeatureTree) -> list[str]:
    """Generate explicit Python constants for feature dimensions and offsets.

    For each feature:
    - Emit dimension constants (FEAT_X, FEAT_Y, FEAT_Z, FEAT_DIAMETER, etc.)
    - Emit pre-computed offset constants (FEAT_OFFSET_X, FEAT_OFFSET_Y)
      derived from placement.alignment or placement.position

    This removes offset arithmetic from the Coder and prevents floating blocks.
    """
    lines: list[str] = []

    for fid in ft.build_order:
        feature = ft.features.get(fid)
        if not feature:
            continue

        prefix = fid.upper().replace("-", "_").replace(" ", "_")
        emitted = False

        # --- Dimension constants ---
        parent_feat = ft.features.get(feature.parent) if feature.parent else None
        parent_params = (parent_feat.params or {}) if parent_feat else {}
        parent_prefix = feature.parent.upper().replace("-", "_") if feature.parent else ""

        is_slot = feature.type.lower() in ("slot", "groove")

        for k, v in (feature.params or {}).items():
            if isinstance(v, (int, float)) and v > 0:
                const_name = f"{prefix}_{k.upper()}"
                lines.append(f"{const_name} = {v}")
                emitted = True
                # If slot/groove has explicit length, also emit ANGLE constant
                if is_slot and k == "length":
                    slot_axis = _detect_slot_axis(feature)
                    angle = 90 if slot_axis == "Y" else 0
                    lines.append(f"{prefix}_ANGLE = {angle}  # slot2D angle: {angle}° = along {slot_axis}-axis")
                    emitted = True
            elif v is None and k == "length":
                # Slot/groove length=null → full parent dimension along slot direction
                slot_axis = _detect_slot_axis(feature)
                if slot_axis == "Y" and parent_params.get("y"):
                    parent_dim_val = float(parent_params["y"])
                    parent_dim_name = f"{parent_prefix}_Y" if parent_prefix else str(parent_dim_val)
                    lines.append(f"{prefix}_LENGTH = {parent_dim_name}  # full parent Y (Nut entlang Y)")
                    lines.append(f"{prefix}_ANGLE = 90  # slot2D angle: 90° = along Y-axis")
                    emitted = True
                elif slot_axis == "X" and parent_params.get("x"):
                    parent_dim_val = float(parent_params["x"])
                    parent_dim_name = f"{parent_prefix}_X" if parent_prefix else str(parent_dim_val)
                    lines.append(f"{prefix}_LENGTH = {parent_dim_name}  # full parent X (Nut entlang X)")
                    lines.append(f"{prefix}_ANGLE = 0  # slot2D angle: 0° = along X-axis (default)")
                    emitted = True
                elif parent_params.get("y"):
                    # Fallback: default to Y axis
                    parent_dim_val = float(parent_params["y"])
                    parent_dim_name = f"{parent_prefix}_Y" if parent_prefix else str(parent_dim_val)
                    lines.append(f"{prefix}_LENGTH = {parent_dim_name}  # full parent Y (Nut entlang Y)")
                    lines.append(f"{prefix}_ANGLE = 90  # slot2D angle: 90° = along Y-axis")
                    emitted = True
                elif parent_params.get("x"):
                    parent_dim_val = float(parent_params["x"])
                    parent_dim_name = f"{parent_prefix}_X" if parent_prefix else str(parent_dim_val)
                    lines.append(f"{prefix}_LENGTH = {parent_dim_name}  # full parent X (Nut entlang X)")
                    lines.append(f"{prefix}_ANGLE = 0  # slot2D angle: 0° = along X-axis")
                    emitted = True

        # --- Offset constants from placement ---
        placement = feature.placement
        if placement and feature.parent:
            parent = ft.features.get(feature.parent)
            offset_x: float | None = None
            offset_y: float | None = None

            # 0. Explicit numeric offset_x/offset_y fields (highest priority)
            if placement.offset_x is not None:
                offset_x = placement.offset_x
            if placement.offset_y is not None:
                offset_y = placement.offset_y

            pos = placement.position  # e.g. "center", "offset(25, 0)", "corner_TR"
            alignment = placement.alignment or ""  # e.g. "flush_right", "centered"

            parent_params_c = (parent.params or {}) if parent else {}
            feat_params_c = feature.params or {}
            pw_c = float(parent_params_c.get("x") or 0)
            pl_c = float(parent_params_c.get("y") or 0)
            fw_c = float(feat_params_c.get("x") or 0)
            fl_c = float(feat_params_c.get("y") or 0)

            # 1. Alignment FIRST — highest precedence (flush_right etc. override "center")
            if alignment and alignment not in ("centered", ""):
                if alignment == "flush_right" and pw_c and fw_c:
                    offset_x = pw_c / 2 - fw_c / 2
                elif alignment == "flush_left" and pw_c and fw_c:
                    offset_x = -(pw_c / 2 - fw_c / 2)
                elif alignment == "flush_top" and pl_c and fl_c:
                    offset_y = pl_c / 2 - fl_c / 2
                elif alignment == "flush_bottom" and pl_c and fl_c:
                    offset_y = -(pl_c / 2 - fl_c / 2)
                elif alignment in ("flush_right_top", "corner_TR") and pw_c and fw_c and pl_c and fl_c:
                    offset_x = pw_c / 2 - fw_c / 2
                    offset_y = pl_c / 2 - fl_c / 2
                elif alignment in ("flush_right_bottom", "corner_BR") and pw_c and fw_c and pl_c and fl_c:
                    offset_x = pw_c / 2 - fw_c / 2
                    offset_y = -(pl_c / 2 - fl_c / 2)
                elif alignment in ("flush_left_top", "corner_TL") and pw_c and fw_c and pl_c and fl_c:
                    offset_x = -(pw_c / 2 - fw_c / 2)
                    offset_y = pl_c / 2 - fl_c / 2
                elif alignment in ("flush_left_bottom", "corner_BL") and pw_c and fw_c and pl_c and fl_c:
                    offset_x = -(pw_c / 2 - fw_c / 2)
                    offset_y = -(pl_c / 2 - fl_c / 2)

            # 2. Explicit offset(dx, dy) from position string (only if alignment didn't resolve)
            if offset_x is None and offset_y is None and pos:
                m = re.match(r"offset\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)", str(pos))
                if m:
                    offset_x = float(m.group(1))
                    offset_y = float(m.group(2))

            # 3. Corner positions from position string
            if offset_x is None and pos in ("corner_TR", "corner_TL", "corner_BR", "corner_BL"):
                if pw_c and fw_c:
                    offset_x = (pw_c / 2 - fw_c / 2) if "R" in pos else -(pw_c / 2 - fw_c / 2)
                if pl_c and fl_c:
                    offset_y = (pl_c / 2 - fl_c / 2) if "T" in pos else -(pl_c / 2 - fl_c / 2)

            # 4. Center fallback (only when nothing else resolved)
            if offset_x is None and offset_y is None and pos == "center":
                offset_x, offset_y = 0.0, 0.0

            # 5. If one axis resolved but the other didn't, default the other to 0
            #    (centered on that axis). Prevents missing OFFSET_Y constants.
            if offset_x is not None and offset_y is None:
                offset_y = 0.0
            elif offset_y is not None and offset_x is None:
                offset_x = 0.0

            if offset_x is not None:
                lines.append(f"{prefix}_OFFSET_X = {round(offset_x, 4)}")
                emitted = True
            if offset_y is not None:
                lines.append(f"{prefix}_OFFSET_Y = {round(offset_y, 4)}")
                emitted = True

        if emitted:
            lines.append("")  # blank line between feature blocks

    return lines


# ------------------------------------------------------------------
# Sub-assembly grouping
# ------------------------------------------------------------------

def _build_sub_assembly_groups(ft: FeatureTree) -> dict:
    """Group features into sub-assemblies for the "build separate, combine later" pattern.

    Returns dict with:
      root_id:       ID of the root feature
      base_subtracts: list of feature IDs that subtract directly from root (before union)
      sub_assemblies: list of dicts, each with:
        root_fid:     ID of the add-feature that starts this sub-assembly
        children:     list of feature IDs that operate on this sub-assembly part
        parent_face:  face on parent where this part gets placed
        parent_z:     Z height of the parent (for translate)
    """
    root_id = None
    for fid in ft.build_order:
        f = ft.features.get(fid)
        if f and f.parent is None:
            root_id = fid
            break
    if not root_id:
        return {"root_id": None, "base_subtracts": [], "sub_assemblies": []}

    # Build parent→children map
    children_of: dict[str, list[str]] = {}
    for fid in ft.build_order:
        f = ft.features.get(fid)
        if f and f.parent:
            children_of.setdefault(f.parent, []).append(fid)

    # Collect all descendants of a feature (recursive)
    def _descendants(fid: str) -> list[str]:
        result = []
        for child in children_of.get(fid, []):
            result.append(child)
            result.extend(_descendants(child))
        return result

    # Categorize root's direct children
    base_subtracts: list[str] = []
    sub_assemblies: list[dict] = []

    for child_fid in children_of.get(root_id, []):
        child = ft.features.get(child_fid)
        if not child:
            continue

        if child.operation == "add":
            # This starts a sub-assembly
            sub_children = _descendants(child_fid)
            face = child.placement.face if child.placement else ">Z"
            root_params = (ft.features[root_id].params or {})
            parent_z = float(root_params.get("z", root_params.get("height", 0)))
            sub_assemblies.append({
                "root_fid": child_fid,
                "children": sub_children,
                "parent_face": face,
                "parent_z": parent_z,
            })
        else:
            base_subtracts.append(child_fid)

    return {
        "root_id": root_id,
        "base_subtracts": base_subtracts,
        "sub_assemblies": sub_assemblies,
    }


def _is_sub_assembly_eligible(groups: dict) -> bool:
    """Check if the blueprint benefits from sub-assembly pattern.

    Sub-assembly is used when there's at least one add-feature on root
    that has child features (holes, chamfers etc.).
    Simple add without children doesn't benefit (no face ambiguity).
    """
    for sa in groups.get("sub_assemblies", []):
        if sa["children"]:
            return True
    return False


# ------------------------------------------------------------------
# Skeleton generator
# ------------------------------------------------------------------

def generate_skeleton(blueprint: dict) -> str:
    """Generate a Python skeleton from a Feature Tree blueprint.

    Uses **sub-assembly pattern** when possible:
      - Each add-feature on root becomes a standalone part
      - Child features (holes, chamfers) are applied to the standalone part
      - Parts are positioned via .translate() and .union() at the end
      - This avoids CadQuery face-selection ambiguity after boolean union

    Falls back to linear pattern (NearestToPointSelector) when sub-assembly
    isn't applicable (e.g., no add-features with children).

    Returns empty string if blueprint is not Feature Tree format.
    """
    if not FeatureTree.is_feature_tree(blueprint):
        return ""

    try:
        ft = FeatureTree.from_dict(blueprint)
    except Exception as e:
        log.error("function_decomposer_parse_failed", error=str(e))
        return ""

    groups = _build_sub_assembly_groups(ft)

    if _is_sub_assembly_eligible(groups):
        return _generate_sub_assembly_skeleton(ft, groups)
    else:
        return _generate_linear_skeleton(ft)


def _generate_sub_assembly_skeleton(ft: FeatureTree, groups: dict) -> str:
    """Generate skeleton using the sub-assembly pattern.

    Pattern:
      1. make_base() → standalone root body
      2. build_<part>() → standalone sub-assembly (create part + apply features)
      3. assemble() → apply base features, then translate+union sub-assemblies
    """
    param_lines = _generate_param_constants(ft)
    root_id = groups["root_id"]
    root_feature = ft.features[root_id]
    root_params = root_feature.params or {}
    root_z = float(root_params.get("z", root_params.get("height", 0)))

    # Collect all features in sub-assemblies (for generating "part" functions)
    sub_assembly_fids: set[str] = set()
    for sa in groups["sub_assemblies"]:
        sub_assembly_fids.add(sa["root_fid"])
        sub_assembly_fids.update(sa["children"])

    lines = [
        "import cadquery as cq",
        "import math",
        "",
        f"# Model: {ft.description}",
        f"# Build Order: {' -> '.join(ft.build_order)}",
        f"# Pattern: SUB-ASSEMBLY (parts built separately, then combined)",
        "",
        'OUTPUT_PATH = "output.stl"  # overwritten by executor',
        "",
        "# PARAMETERS — pre-computed from blueprint (Coder: do NOT change these values)",
    ] + param_lines + [""]

    func_map: dict[str, str] = {}

    # --- Root function ---
    fname_root = _function_name(root_feature)
    func_map[root_id] = fname_root
    lines.append(f"def {fname_root}() -> cq.Workplane:")
    lines.append(_make_docstring(root_feature))
    lines.append("    # Root body: use cq.Workplane('XY').box() or .cylinder()")
    lines.append("    # centered=(True, True, False) → Z starts at 0, goes to height")
    lines.append("    pass")
    lines.append("")

    # --- Direct subtract functions on root (applied BEFORE union) ---
    for fid in groups["base_subtracts"]:
        feature = ft.features.get(fid)
        if not feature:
            continue
        fname = _function_name(feature)
        func_map[fid] = fname
        lines.append(f"def {fname}(body: cq.Workplane) -> cq.Workplane:")
        lines.append(_make_docstring(feature))
        lines.append("    # ★ Applied to base BEFORE any union — face selection is unambiguous")
        lines.append("    # TODO: Coder fills in")
        lines.append("    pass")
        lines.append("")

    # --- Sub-assembly part creation functions ---
    for sa in groups["sub_assemblies"]:
        sa_root_fid = sa["root_fid"]
        sa_root = ft.features[sa_root_fid]
        sa_params = sa_root.params or {}
        sa_prefix = sa_root_fid.upper().replace("-", "_").replace(" ", "_")

        # Part creation: make_<part>() → standalone body
        make_name = f"make_{sa_root_fid}"
        func_map[sa_root_fid] = make_name
        lines.append(f"def {make_name}() -> cq.Workplane:")
        lines.append(f'    """Create standalone {sa_root_fid} body.')
        lines.append(f"    Type: {sa_root.type}")
        p_str = ", ".join(f"{k}={v}" for k, v in sa_params.items())
        lines.append(f"    Params: {p_str}")
        lines.append(f'    """')
        lines.append(f"    # ★ Build as STANDALONE part at origin — same as make_base()")
        lines.append(f"    # cq.Workplane('XY').box({sa_prefix}_X, {sa_prefix}_Y, {sa_prefix}_Z, centered=(True, True, False))")
        lines.append(f"    pass")
        lines.append("")

        # Child feature functions: operate on the standalone part
        for child_fid in sa["children"]:
            child = ft.features.get(child_fid)
            if not child:
                continue
            child_fname = _function_name(child)
            func_map[child_fid] = child_fname
            lines.append(f"def {child_fname}(part: cq.Workplane) -> cq.Workplane:")
            lines.append(_make_docstring(child))
            lines.append(f"    # ★ Operating on STANDALONE part — face selection is unambiguous!")
            lines.append(f"    # Use: part.faces(\"{child.placement.face if child.placement else '>Z'}\").workplane(centerOption='CenterOfBoundBox')")
            lines.append(f"    # TODO: Coder fills in")
            lines.append(f"    pass")
            lines.append("")

        # build_<part>() — composes make + child features
        build_name = f"build_{sa_root_fid}"
        lines.append(f"def {build_name}() -> cq.Workplane:")
        lines.append(f'    """Build {sa_root_fid} sub-assembly: create part + apply all features."""')
        lines.append(f"    part = {make_name}()")
        for child_fid in sa["children"]:
            child_fname = func_map.get(child_fid, f"apply_{child_fid}")
            lines.append(f"    part = {child_fname}(part)")
        lines.append(f"    return part")
        lines.append("")

    # --- assemble() ---
    lines.append("")
    lines.append("# === ASSEMBLY ===")
    lines.append("def assemble() -> cq.Workplane:")
    lines.append(f'    """Assemble: build parts separately, then position + combine.')
    lines.append(f"")
    lines.append(f"    Pattern: sub-assembly (no face-ambiguity after union)")
    lines.append(f"    1. Build base + apply direct features (holes etc.)")
    lines.append(f"    2. Build each sub-assembly (standalone part + its features)")
    lines.append(f"    3. Translate sub-assemblies to correct position")
    lines.append(f"    4. Union everything together")
    lines.append(f'    """')

    # Phase 1: base + direct subtracts
    lines.append(f"    result = {func_map[root_id]}()")
    for fid in groups["base_subtracts"]:
        fname = func_map.get(fid)
        if fname:
            lines.append(f"    result = {fname}(result)")

    # Phase 2+3: build sub-assemblies + translate + union
    for sa in groups["sub_assemblies"]:
        sa_root_fid = sa["root_fid"]
        sa_prefix = sa_root_fid.upper().replace("-", "_").replace(" ", "_")
        sa_feature = ft.features[sa_root_fid]
        face = sa.get("parent_face", ">Z")

        lines.append(f"")
        lines.append(f"    # --- Sub-assembly: {sa_root_fid} ---")
        lines.append(f"    {sa_root_fid} = build_{sa_root_fid}()")

        # Translate to position
        if face == ">Z":
            lines.append(
                f"    {sa_root_fid} = {sa_root_fid}.translate(("
                f"{sa_prefix}_OFFSET_X, {sa_prefix}_OFFSET_Y, "
                f"{root_id.upper().replace('-', '_')}_{_z_param_name(root_params)}))"
            )
        elif face == "<Z":
            sa_params = sa_feature.params or {}
            sa_z = float(sa_params.get("z", sa_params.get("height", 0)))
            lines.append(
                f"    {sa_root_fid} = {sa_root_fid}.translate(("
                f"{sa_prefix}_OFFSET_X, {sa_prefix}_OFFSET_Y, -{sa_prefix}_{_z_param_name(sa_params)}))"
            )
        else:
            # Side face placement — compute correct translate for the face
            root_prefix = root_id.upper().replace("-", "_").replace(" ", "_")
            sa_feature = ft.features[sa_root_fid]
            sa_params = sa_feature.params or {}
            root_z_param = _z_param_name(root_params)
            sa_y_dim = sa_params.get("y", sa_params.get("height", 0))
            sa_x_dim = sa_params.get("x", 0)
            sa_z_dim = sa_params.get("z", sa_params.get("height", 0))

            if face == ">Y":
                # Back face: translate Y to parent back edge
                lines.append(
                    f"    # ★ Back-face placement ({face}): translate to back edge of parent"
                )
                lines.append(
                    f"    {sa_root_fid} = {sa_root_fid}.translate(("
                    f"{sa_prefix}_OFFSET_X, "
                    f"{root_prefix}_Y/2 - {sa_prefix}_Y/2, "
                    f"{root_prefix}_{root_z_param}))"
                )
            elif face == "<Y":
                # Front face: translate Y to parent front edge
                lines.append(
                    f"    # ★ Front-face placement ({face}): translate to front edge of parent"
                )
                lines.append(
                    f"    {sa_root_fid} = {sa_root_fid}.translate(("
                    f"{sa_prefix}_OFFSET_X, "
                    f"-({root_prefix}_Y/2 - {sa_prefix}_Y/2), "
                    f"{root_prefix}_{root_z_param}))"
                )
            elif face == ">X":
                # Right face: translate X to parent right edge
                lines.append(
                    f"    # ★ Right-face placement ({face}): translate to right edge of parent"
                )
                lines.append(
                    f"    {sa_root_fid} = {sa_root_fid}.translate(("
                    f"{root_prefix}_X/2 - {sa_prefix}_X/2, "
                    f"{sa_prefix}_OFFSET_Y, "
                    f"{root_prefix}_{root_z_param}))"
                )
            elif face == "<X":
                # Left face: translate X to parent left edge
                lines.append(
                    f"    # ★ Left-face placement ({face}): translate to left edge of parent"
                )
                lines.append(
                    f"    {sa_root_fid} = {sa_root_fid}.translate(("
                    f"-({root_prefix}_X/2 - {sa_prefix}_X/2), "
                    f"{sa_prefix}_OFFSET_Y, "
                    f"{root_prefix}_{root_z_param}))"
                )
            else:
                # Unknown face — fallback with TODO
                lines.append(
                    f"    {sa_root_fid} = {sa_root_fid}.translate(("
                    f"{sa_prefix}_OFFSET_X, {sa_prefix}_OFFSET_Y, "
                    f"{root_prefix}_{root_z_param}))  # TODO: adjust for {face} face"
                )

        lines.append(f"    result = result.union({sa_root_fid}).clean()")

    lines.append(f"")
    lines.append(f"    return result")
    lines.append("")
    lines.append("")
    lines.append("result = assemble()")
    lines.append("cq.exporters.export(result, OUTPUT_PATH)")

    if ft.notes:
        lines.append(f"# Notes: {ft.notes}")

    return "\n".join(lines)


def _z_param_name(params: dict) -> str:
    """Return the parameter name used for height (Z or HEIGHT)."""
    if "z" in params:
        return "Z"
    return "HEIGHT"


def _generate_linear_skeleton(ft: FeatureTree) -> str:
    """Generate skeleton using the linear pattern (original approach).

    Used when sub-assembly pattern isn't beneficial (no add-features with children).
    Falls back to NearestToPointSelector for face disambiguation.
    """
    positions = _compute_feature_positions(ft)
    ntp_features = _features_needing_ntp(ft)
    has_ntp = bool(ntp_features)

    param_lines = _generate_param_constants(ft)

    # Generate SELECTOR_POINT constants for features that need NTP
    selector_lines: list[str] = []
    if ntp_features:
        selector_lines.append("")
        selector_lines.append("# SELECTOR POINTS — NearestToPointSelector targets (Coder: do NOT change)")
        for fid in ft.build_order:
            if fid not in ntp_features:
                continue
            feature = ft.features.get(fid)
            if not feature or not feature.placement:
                continue
            parent_pos = positions.get(feature.parent)
            if not parent_pos:
                continue
            face = feature.placement.face or ">Z"
            point = _face_center_point(parent_pos, face)
            if point:
                prefix = fid.upper().replace("-", "_").replace(" ", "_")
                px, py, pz = (round(v, 2) for v in point)
                selector_lines.append(
                    f"{prefix}_SELECTOR_POINT = ({px}, {py}, {pz})"
                )
        selector_lines.append("")

    import_lines = ["import cadquery as cq"]
    if has_ntp:
        import_lines.append("from cadquery.selectors import NearestToPointSelector")
    import_lines.append("import math")

    lines = import_lines + [
        "",
        f"# Model: {ft.description}",
        f"# Build Order: {' -> '.join(ft.build_order)}",
        "",
        'OUTPUT_PATH = "output.stl"  # overwritten by executor',
        "",
        "# PARAMETERS — pre-computed from blueprint (Coder: do NOT change these values)",
    ] + param_lines + selector_lines + [""]

    func_map: dict[str, str] = {}

    for fid in ft.build_order:
        feature = ft.features.get(fid)
        if not feature:
            continue

        fname = _function_name(feature)
        func_map[fid] = fname
        fid_needs_ntp = fid in ntp_features

        if feature.parent is None:
            lines.append(f"def {fname}() -> cq.Workplane:")
            lines.append(_make_docstring(feature))
            lines.append("    # Root body: use cq.Workplane('XY').box() or .cylinder()")
            lines.append("    # centered=(True, True, False) → Z starts at 0, goes to height")
            lines.append("    pass")
        else:
            lines.append(f"def {fname}(body: cq.Workplane) -> cq.Workplane:")
            lines.append(_make_docstring(feature, needs_ntp=fid_needs_ntp))
            if feature.operation == "add":
                lines.append("    # Use: body.faces(face).workplane(centerOption='CenterOfBoundBox').center(ox,oy).rect(W,L).extrude(H)")
            if fid_needs_ntp:
                prefix = fid.upper().replace("-", "_").replace(" ", "_")
                face = feature.placement.face if feature.placement else ">Z"
                lines.append(f"    # ★★ AFTER UNION: body.faces(NearestToPointSelector({prefix}_SELECTOR_POINT)).workplane(centerOption='CenterOfBoundBox')")
            lines.append("    # TODO: Coder fills in")
            lines.append("    pass")
        lines.append("")

    # --- assemble() ---
    lines.append("")
    lines.append("# === ASSEMBLY ===")
    lines.append("def assemble() -> cq.Workplane:")
    lines.append('    """Assemble all features in build order."""')

    root_ids = [
        fid for fid in ft.build_order
        if ft.features.get(fid) and ft.features[fid].parent is None
    ]

    if root_ids:
        first = root_ids[0]
        lines.append(f"    result = {func_map[first]}()")
        for fid in ft.build_order:
            if fid == first:
                continue
            fname = func_map.get(fid)
            if fname:
                lines.append(f"    result = {fname}(result)")
    else:
        lines.append("    result = None  # ERROR: no root feature in build_order")

    lines.append("    return result")
    lines.append("")
    lines.append("")
    lines.append("result = assemble()")
    lines.append("cq.exporters.export(result, OUTPUT_PATH)")

    if ft.notes:
        lines.append(f"# Notes: {ft.notes}")

    return "\n".join(lines)


# ------------------------------------------------------------------
# Agent wrapper
# ------------------------------------------------------------------

class FunctionDecomposerAgent:
    """Generates a Python skeleton from a Feature Tree blueprint.

    Rule-based — no LLM call. Takes state.blueprint (Feature Tree format)
    and writes the skeleton to state.code_skeleton.

    If the blueprint is not Feature Tree format, writes empty string
    so the Coder falls back to legacy CSG-Tree code generation.
    """

    name = "function_decomposer"

    def __init__(self):
        self.log = structlog.get_logger().bind(agent=self.name)

    def decompose(self, state: PipelineState) -> dict:
        blueprint = state.get("blueprint", {})

        if not FeatureTree.is_feature_tree(blueprint):
            self.log.info("function_decomposer_skipped",
                          reason="not_feature_tree",
                          keys=list(blueprint.keys())[:5])
            return {"code_skeleton": "", "generation_mode": "llm"}

        build_order = blueprint.get("build_order", [])

        # Classify: all standard → template, mixed, or llm-only
        mode = classify_blueprint(blueprint)

        if mode == "template":
            # All features are standard — generate complete deterministic code.
            # Coder will be skipped entirely.
            code = generate_template_code(blueprint)
            self.log.info("function_decomposer_template",
                          features=len(build_order),
                          code_lines=len(code.splitlines()))
            return {"code": code, "code_skeleton": "", "generation_mode": "template"}

        if mode == "mixed":
            # Standard features get template code with `pass` stubs for complex ones.
            # Coder only fills in the stubs.
            code_with_stubs = generate_template_code(blueprint)
            self.log.info("function_decomposer_mixed",
                          features=len(build_order),
                          skeleton_lines=len(code_with_stubs.splitlines()))
            return {"code_skeleton": code_with_stubs, "generation_mode": "mixed"}

        # mode == "llm" — all complex, fall back to legacy skeleton
        if len(build_order) <= 1:
            self.log.info("function_decomposer_skipped",
                          reason="single_feature",
                          features=len(build_order))
            return {"code_skeleton": "", "generation_mode": "llm"}

        skeleton = generate_skeleton(blueprint)

        if skeleton:
            self.log.info("function_decomposer_done",
                          features=len(build_order),
                          skeleton_lines=len(skeleton.splitlines()))
        else:
            self.log.warning("function_decomposer_empty_skeleton")

        return {"code_skeleton": skeleton, "generation_mode": "llm"}
