"""
src/codegen/assembler/ — Assembles CadQuery code from Feature Tree + templates.

Takes a resolved Feature Tree blueprint (with pre-computed offsets) and
generates a complete, executable Python file using templates.

For standard features: deterministic template code.
For complex features: function stubs with `pass` (LLM fills these).

═══════════════════════════════════════════════════════════════════
STRUKTUR (bei Aenderungen pflegen! Siehe CLAUDE.md)
═══════════════════════════════════════════════════════════════════
Public API (core.py):
  generate_code(blueprint)        — Blueprint → fertige .py-Datei als str
  _make_func_name                 — fid → make_/drill_/cut_/apply_ Prefix

Code-Generierungs-Phasen (orchestriert von generate_code):
  Phase 1: _generate_constants    — Konstanten pro Feature (DIMS, OFFSETS)
  Phase 2: _generate_root / _generate_add_part / _generate_subtract
                                  — eine make_/cut_/apply_-Funktion pro Feature
  Phase 3: _generate_sub_assembly_builds
                                  — build_<part>() Funktionen
  Phase 4: _generate_assemble     — assemble(): root + sub-assemblies
  Phase 5: main                   — exporters.export(result, OUTPUT_PATH)

Sub-Module (kein direkter Code in core.py):
  .feature_codegen — Phase 1 + 2: per-Feature Code (_generate_constants,
                     _generate_root, _generate_add_part, _generate_subtract,
                     _safe_depth, _find_parent, _grid_layout)
  .assembly        — Phase 3 + 4: _generate_sub_assembly_builds,
                     _generate_assemble, _resolve_part_root
  .transforms      — .rotate()/.translate()-Emitter: _emit_pre_rotation,
                     _emit_face_rotation, _compute_translate
═══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

from .assembly import _generate_assemble, _generate_sub_assembly_builds
from .feature_codegen import (
    _generate_add_part,
    _generate_constants,
    _generate_root,
    _generate_subtract,
)


def generate_code(blueprint: dict) -> str:
    """Generate complete CadQuery Python code from a Feature Tree blueprint.

    Returns a complete, executable Python file as a string.
    Complex features get `pass` stubs for LLM to fill.
    """
    build_order = blueprint.get("build_order", [])
    features = blueprint.get("features", {})

    if not build_order or not features:
        return ""

    # Identify root and sub-assembly structure
    root_id = build_order[0]

    # Collect all parts
    lines: list[str] = []
    lines.append("import cadquery as cq")
    lines.append("from cadquery.selectors import NearestToPointSelector")
    lines.append("")
    lines.append("OUTPUT_PATH = 'output.stl'")
    lines.append("")

    # Phase 1: Generate constants
    const_lines = _generate_constants(build_order, features)
    if const_lines:
        lines.extend(const_lines)
        lines.append("")

    # Phase 2: Generate function definitions
    func_map: dict[str, str] = {}  # fid → func_name
    sub_assemblies: list[dict] = []

    for fid in build_order:
        feat = features.get(fid, {})
        ftype = feat.get("type", "box").lower()
        operation = feat.get("operation", "add").lower()
        parent = feat.get("parent")
        params = feat.get("params", {})
        placement = feat.get("placement") or {}

        func_name = _make_func_name(fid, operation)
        func_map[fid] = func_name

        # Modifiers (fillet, chamfer, shell) are always treated as subtract/modify
        # regardless of what operation field says
        is_modifier = ftype in ("fillet", "chamfer", "shell")

        if parent is None and not is_modifier:
            # Root feature
            code = _generate_root(func_name, ftype, params)
        elif operation in ("add", "union") and not is_modifier:
            # Sub-assembly part — build standalone
            code = _generate_add_part(func_name, ftype, params)
            sub_assemblies.append({
                "fid": fid,
                "func_name": func_name,
                "parent": parent,
                "placement": placement,
                "params": params,
            })
        else:
            # Subtract/modify feature
            code = _generate_subtract(func_name, fid, ftype, params, placement, features)

        if code:
            lines.append(code)
            lines.append("")

    # Phase 3: Generate sub-assembly build functions
    # Group: which subtract features belong to which add-part?
    sa_builds = _generate_sub_assembly_builds(
        build_order, features, func_map, sub_assemblies
    )
    if sa_builds:
        lines.extend(sa_builds)

    # Phase 4: Generate assemble() function
    assemble_lines = _generate_assemble(
        root_id, build_order, features, func_map, sub_assemblies
    )
    lines.extend(assemble_lines)

    # Phase 5: Main
    lines.append("")
    lines.append("result = assemble()")
    lines.append("cq.exporters.export(result, OUTPUT_PATH)")
    lines.append("")

    return "\n".join(lines)


def _make_func_name(fid: str, operation: str) -> str:
    """Generate a function name from feature ID."""
    clean = fid.replace("-", "_").replace(" ", "_")
    if operation in ("subtract", "cut"):
        if clean.startswith(("hole", "drill")):
            return f"drill_{clean}"
        elif clean.startswith(("slot", "groove", "nut")):
            return f"cut_{clean}"
        elif clean.startswith(("fillet", "chamfer")):
            return f"apply_{clean}"
        return f"cut_{clean}"
    return f"make_{clean}"
