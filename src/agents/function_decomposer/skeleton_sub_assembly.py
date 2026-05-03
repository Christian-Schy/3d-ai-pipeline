"""Sub-assembly skeleton — each part built standalone, then translated + unioned.

Avoids CadQuery face-selection ambiguity that arises after boolean union:
features on a sub-assembly are applied to its standalone body, then the
finished part is positioned and merged into the result.
"""

from src.graph.feature_tree import FeatureTree, FeatureEntry

from .constants import generate_param_constants
from .docstrings import make_docstring
from .grouping import AssemblyGroups, SubAssembly
from .naming import function_name, prefix_for
from .positions import z_param_name


def generate_sub_assembly_skeleton(ft: FeatureTree, groups: AssemblyGroups) -> str:
    """Emit a skeleton that builds each sub-assembly part separately.

    Layout:
      1. make_<root>()                      → root body
      2. drill_/cut_/... functions          → applied to root BEFORE union
      3. make_<part>() / per-feature funcs  → standalone sub-assembly part
      4. build_<part>()                     → composes part + features
      5. assemble()                         → translate + union everything
    """
    root_id = groups.root_id
    if root_id is None:
        return ""

    root_feature = ft.features[root_id]
    root_params = root_feature.params or {}

    func_map: dict[str, str] = {}
    lines: list[str] = []

    lines.extend(_emit_header(ft))
    lines.extend(generate_param_constants(ft))
    lines.append("")

    lines.extend(_emit_root(root_feature, func_map))
    lines.extend(_emit_base_subtracts(ft, groups.base_subtracts, func_map))

    for sa in groups.sub_assemblies:
        lines.extend(_emit_sub_assembly_block(ft, sa, func_map))

    lines.extend(_emit_assemble(ft, root_id, root_params, groups, func_map))
    lines.extend(_emit_export(ft))

    return "\n".join(lines)


# ────────────────────────────────────────────────────────────────────
# Section emitters
# ────────────────────────────────────────────────────────────────────

def _emit_header(ft: FeatureTree) -> list[str]:
    return [
        "import cadquery as cq",
        "import math",
        "",
        f"# Model: {ft.description}",
        f"# Build Order: {' -> '.join(ft.build_order)}",
        "# Pattern: SUB-ASSEMBLY (parts built separately, then combined)",
        "",
        'OUTPUT_PATH = "output.stl"  # overwritten by executor',
        "",
        "# PARAMETERS — pre-computed from blueprint (Coder: do NOT change these values)",
    ]


def _emit_root(root: FeatureEntry, func_map: dict[str, str]) -> list[str]:
    fname = function_name(root)
    func_map[root.id] = fname
    return [
        f"def {fname}() -> cq.Workplane:",
        make_docstring(root),
        "    # Root body: use cq.Workplane('XY').box() or .cylinder()",
        "    # centered=(True, True, False) → Z starts at 0, goes to height",
        "    pass",
        "",
    ]


def _emit_base_subtracts(
    ft: FeatureTree, base_subtracts: list[str], func_map: dict[str, str],
) -> list[str]:
    out: list[str] = []
    for fid in base_subtracts:
        feature = ft.features.get(fid)
        if not feature:
            continue
        fname = function_name(feature)
        func_map[fid] = fname
        out.extend([
            f"def {fname}(body: cq.Workplane) -> cq.Workplane:",
            make_docstring(feature),
            "    # ★ Applied to base BEFORE any union — face selection is unambiguous",
            "    # TODO: Coder fills in",
            "    pass",
            "",
        ])
    return out


def _emit_sub_assembly_block(
    ft: FeatureTree, sa: SubAssembly, func_map: dict[str, str],
) -> list[str]:
    sa_root = ft.features[sa.root_fid]
    sa_params = sa_root.params or {}
    sa_prefix = prefix_for(sa.root_fid)
    out: list[str] = []

    # Standalone part creator
    make_name = f"make_{sa.root_fid}"
    func_map[sa.root_fid] = make_name
    out.extend([
        f"def {make_name}() -> cq.Workplane:",
        f'    """Create standalone {sa.root_fid} body.',
        f"    Type: {sa_root.type}",
        f"    Params: {', '.join(f'{k}={v}' for k, v in sa_params.items())}",
        '    """',
        "    # ★ Build as STANDALONE part at origin — same as make_base()",
        f"    # cq.Workplane('XY').box({sa_prefix}_X, {sa_prefix}_Y, {sa_prefix}_Z, centered=(True, True, False))",
        "    pass",
        "",
    ])

    # Per-child feature functions on the standalone part
    for child_fid in sa.children:
        child = ft.features.get(child_fid)
        if not child:
            continue
        cname = function_name(child)
        func_map[child_fid] = cname
        face = child.placement.face if child.placement else ">Z"
        out.extend([
            f"def {cname}(part: cq.Workplane) -> cq.Workplane:",
            make_docstring(child),
            "    # ★ Operating on STANDALONE part — face selection is unambiguous!",
            f'    # Use: part.faces("{face}").workplane(centerOption=\'CenterOfBoundBox\')',
            "    # TODO: Coder fills in",
            "    pass",
            "",
        ])

    # Composer that chains part + features together
    build_name = f"build_{sa.root_fid}"
    out.append(f"def {build_name}() -> cq.Workplane:")
    out.append(f'    """Build {sa.root_fid} sub-assembly: create part + apply all features."""')
    out.append(f"    part = {make_name}()")
    for child_fid in sa.children:
        cname = func_map.get(child_fid, f"apply_{child_fid}")
        out.append(f"    part = {cname}(part)")
    out.append("    return part")
    out.append("")
    return out


def _emit_assemble(
    ft: FeatureTree,
    root_id: str,
    root_params: dict,
    groups: AssemblyGroups,
    func_map: dict[str, str],
) -> list[str]:
    out = [
        "",
        "# === ASSEMBLY ===",
        "def assemble() -> cq.Workplane:",
        '    """Assemble: build parts separately, then position + combine.',
        "",
        "    Pattern: sub-assembly (no face-ambiguity after union)",
        "    1. Build base + apply direct features (holes etc.)",
        "    2. Build each sub-assembly (standalone part + its features)",
        "    3. Translate sub-assemblies to correct position",
        "    4. Union everything together",
        '    """',
        f"    result = {func_map[root_id]}()",
    ]
    for fid in groups.base_subtracts:
        fname = func_map.get(fid)
        if fname:
            out.append(f"    result = {fname}(result)")

    for sa in groups.sub_assemblies:
        out.append("")
        out.append(f"    # --- Sub-assembly: {sa.root_fid} ---")
        out.append(f"    {sa.root_fid} = build_{sa.root_fid}()")
        out.extend(_emit_translate(root_id, root_params, ft, sa))
        out.append(f"    result = result.union({sa.root_fid}).clean()")

    out.append("")
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


# ────────────────────────────────────────────────────────────────────
# Translate emission per face
# ────────────────────────────────────────────────────────────────────

# Side-face translate templates. Tuple is (side_word, x_expr, y_expr) where
# side_word is used in the comment ("translate to {side_word} edge of parent")
# and the expressions use {root_prefix} / {sa_prefix} for substitution.
# z is always {root_prefix}_{root_z_param} (top of root).
_SIDE_FACE_TRANSLATES: dict[str, tuple[str, str, str]] = {
    ">Y": ("back",  "{sa_prefix}_OFFSET_X",
           "{root_prefix}_Y/2 - {sa_prefix}_Y/2"),
    "<Y": ("front", "{sa_prefix}_OFFSET_X",
           "-({root_prefix}_Y/2 - {sa_prefix}_Y/2)"),
    ">X": ("right",
           "{root_prefix}_X/2 - {sa_prefix}_X/2", "{sa_prefix}_OFFSET_Y"),
    "<X": ("left",
           "-({root_prefix}_X/2 - {sa_prefix}_X/2)", "{sa_prefix}_OFFSET_Y"),
}


def _emit_translate(
    root_id: str, root_params: dict, ft: FeatureTree, sa: SubAssembly,
) -> list[str]:
    """Emit the .translate(...) line(s) for one sub-assembly's positioning."""
    sa_prefix = prefix_for(sa.root_fid)
    sa_feature = ft.features[sa.root_fid]
    sa_params = sa_feature.params or {}
    face = sa.parent_face

    # Top of root (>Z): translate by full root height. Legacy quirk —
    # only dashes are stripped from the root id here (no space stripping),
    # preserved to keep the emitted code byte-identical.
    if face == ">Z":
        legacy_root_prefix = root_id.upper().replace("-", "_")
        return [
            f"    {sa.root_fid} = {sa.root_fid}.translate(("
            f"{sa_prefix}_OFFSET_X, {sa_prefix}_OFFSET_Y, "
            f"{legacy_root_prefix}_{z_param_name(root_params)}))"
        ]

    # Bottom of root (<Z): hang the part under the base.
    if face == "<Z":
        return [
            f"    {sa.root_fid} = {sa.root_fid}.translate(("
            f"{sa_prefix}_OFFSET_X, {sa_prefix}_OFFSET_Y, "
            f"-{sa_prefix}_{z_param_name(sa_params)}))"
        ]

    root_prefix = prefix_for(root_id)
    root_z_param = z_param_name(root_params)
    z_expr = f"{root_prefix}_{root_z_param}"

    side = _SIDE_FACE_TRANSLATES.get(face)
    if side is None:
        # Unknown face — fall back with a TODO so executor flags it loudly.
        return [
            f"    {sa.root_fid} = {sa.root_fid}.translate(("
            f"{sa_prefix}_OFFSET_X, {sa_prefix}_OFFSET_Y, "
            f"{z_expr}))  # TODO: adjust for {face} face"
        ]

    side_word, x_tmpl, y_tmpl = side
    x_expr = x_tmpl.format(root_prefix=root_prefix, sa_prefix=sa_prefix)
    y_expr = y_tmpl.format(root_prefix=root_prefix, sa_prefix=sa_prefix)
    return [
        f"    # ★ {side_word.capitalize()}-face placement ({face}): translate to {side_word} edge of parent",
        f"    {sa.root_fid} = {sa.root_fid}.translate(({x_expr}, {y_expr}, {z_expr}))",
    ]
