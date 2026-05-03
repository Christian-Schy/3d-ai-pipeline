"""Linear skeleton — one function per feature, applied in build_order.

Used when the sub-assembly pattern doesn't help (no add-features with
children). Falls back to NearestToPointSelector to disambiguate faces
after boolean unions.
"""

from src.graph.feature_tree import FeatureTree

from .constants import generate_param_constants
from .docstrings import make_docstring
from .naming import function_name, prefix_for
from .positions import (
    compute_feature_positions,
    face_center_point,
    features_needing_ntp,
)


def generate_linear_skeleton(ft: FeatureTree) -> str:
    """Emit a flat skeleton: assemble() chains every per-feature function."""
    positions = compute_feature_positions(ft)
    ntp_features = features_needing_ntp(ft)
    has_ntp = bool(ntp_features)

    lines: list[str] = []
    lines.extend(_emit_imports(has_ntp))
    lines.extend(_emit_header(ft))
    lines.extend(generate_param_constants(ft))
    lines.extend(_emit_selector_constants(ft, positions, ntp_features))
    lines.append("")

    func_map: dict[str, str] = {}
    lines.extend(_emit_feature_functions(ft, ntp_features, func_map))
    lines.extend(_emit_assemble(ft, func_map))
    lines.extend(_emit_export(ft))

    return "\n".join(lines)


# ────────────────────────────────────────────────────────────────────
# Section emitters
# ────────────────────────────────────────────────────────────────────

def _emit_imports(has_ntp: bool) -> list[str]:
    out = ["import cadquery as cq"]
    if has_ntp:
        out.append("from cadquery.selectors import NearestToPointSelector")
    out.append("import math")
    return out


def _emit_header(ft: FeatureTree) -> list[str]:
    return [
        "",
        f"# Model: {ft.description}",
        f"# Build Order: {' -> '.join(ft.build_order)}",
        "",
        'OUTPUT_PATH = "output.stl"  # overwritten by executor',
        "",
        "# PARAMETERS — pre-computed from blueprint (Coder: do NOT change these values)",
    ]


def _emit_selector_constants(
    ft: FeatureTree, positions: dict[str, dict], ntp_features: set[str],
) -> list[str]:
    if not ntp_features:
        return []
    out = [
        "",
        "# SELECTOR POINTS — NearestToPointSelector targets (Coder: do NOT change)",
    ]
    for fid in ft.build_order:
        if fid not in ntp_features:
            continue
        feature = ft.features.get(fid)
        if not feature or not feature.placement:
            continue
        parent_pos = positions.get(feature.parent)
        if not parent_pos:
            continue
        point = face_center_point(parent_pos, feature.placement.face or ">Z")
        if point:
            px, py, pz = (round(v, 2) for v in point)
            out.append(f"{prefix_for(fid)}_SELECTOR_POINT = ({px}, {py}, {pz})")
    out.append("")
    return out


def _emit_feature_functions(
    ft: FeatureTree, ntp_features: set[str], func_map: dict[str, str],
) -> list[str]:
    out: list[str] = []
    for fid in ft.build_order:
        feature = ft.features.get(fid)
        if not feature:
            continue
        fname = function_name(feature)
        func_map[fid] = fname
        needs_ntp = fid in ntp_features

        if feature.parent is None:
            out.append(f"def {fname}() -> cq.Workplane:")
            out.append(make_docstring(feature))
            out.append("    # Root body: use cq.Workplane('XY').box() or .cylinder()")
            out.append("    # centered=(True, True, False) → Z starts at 0, goes to height")
            out.append("    pass")
        else:
            out.append(f"def {fname}(body: cq.Workplane) -> cq.Workplane:")
            out.append(make_docstring(feature, needs_ntp=needs_ntp))
            if feature.operation == "add":
                out.append(
                    "    # Use: body.faces(face).workplane(centerOption='CenterOfBoundBox')"
                    ".center(ox,oy).rect(W,L).extrude(H)"
                )
            if needs_ntp:
                prefix = prefix_for(fid)
                out.append(
                    f"    # ★★ AFTER UNION: body.faces(NearestToPointSelector({prefix}_SELECTOR_POINT))"
                    ".workplane(centerOption='CenterOfBoundBox')"
                )
            out.append("    # TODO: Coder fills in")
            out.append("    pass")
        out.append("")
    return out


def _emit_assemble(ft: FeatureTree, func_map: dict[str, str]) -> list[str]:
    out = [
        "",
        "# === ASSEMBLY ===",
        "def assemble() -> cq.Workplane:",
        '    """Assemble all features in build order."""',
    ]
    root_ids = [
        fid for fid in ft.build_order
        if ft.features.get(fid) and ft.features[fid].parent is None
    ]
    if root_ids:
        first = root_ids[0]
        out.append(f"    result = {func_map[first]}()")
        for fid in ft.build_order:
            if fid == first:
                continue
            fname = func_map.get(fid)
            if fname:
                out.append(f"    result = {fname}(result)")
    else:
        out.append("    result = None  # ERROR: no root feature in build_order")

    out.append("    return result")
    return out


def _emit_export(ft: FeatureTree) -> list[str]:
    out = [
        "",
        "",
        "result = assemble()",
        "cq.exporters.export(result, OUTPUT_PATH)",
    ]
    if ft.notes:
        out.append(f"# Notes: {ft.notes}")
    return out
