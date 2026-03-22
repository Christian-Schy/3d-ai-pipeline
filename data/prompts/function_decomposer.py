# FUNCTION DECOMPOSER — Regelbasierte Template-Engine (KEIN LLM)
# Nimmt den Feature Tree und erzeugt ein Python-Code-Skeleton

"""
Der Function Decomposer ist KEIN LLM-Agent. Er ist eine deterministische
Python-Funktion die aus dem Feature Tree ein Code-Skeleton generiert.
"""


def generate_skeleton(blueprint: dict) -> str:
    """Erzeugt ein Python-Code-Skeleton aus dem Feature Tree Blueprint.

    Args:
        blueprint: Feature Tree JSON vom Planner

    Returns:
        Python-Code als String mit TODO-Markierungen für den Coder
    """
    features = blueprint.get("features", {})
    build_order = blueprint.get("build_order", [])
    description = blueprint.get("description", "3D-Modell")

    lines = []

    # === IMPORTS ===
    lines.append("import cadquery as cq")

    # Check if NearestToPointSelector needed
    needs_ntp = any(
        f.get("placement", {}).get("face") == "NearestToPoint"
        or f.get("placement", {}).get("selector_hint") == "after_union"
        for f in features.values()
        if isinstance(f, dict)
    )
    if needs_ntp:
        lines.append("from cadquery.selectors import NearestToPointSelector")

    # Check if math needed (circular patterns)
    needs_math = any(
        f.get("type") in ("hole_pattern_circular",
                           "pattern_polar")
        for f in features.values()
        if isinstance(f, dict)
    )
    if needs_math:
        lines.append("import math")

    lines.append("")
    lines.append(f'OUTPUT_PATH = "output.stl"')
    lines.append("")

    # === PARAMETER ===
    lines.append("# " + "=" * 60)
    lines.append("# PARAMETER")
    lines.append("# " + "=" * 60)

    for fid in build_order:
        feat = features.get(fid, {})
        params = feat.get("params", {})
        prefix = fid.upper()
        for key, val in params.items():
            if val is not None:
                const_name = f"{prefix}_{key.upper()}"
                lines.append(f"{const_name} = {val}")
    lines.append("")

    # === FEATURE FUNCTIONS ===
    lines.append("# " + "=" * 60)
    lines.append("# FEATURE-FUNKTIONEN")
    lines.append("# " + "=" * 60)
    lines.append("")

    for fid in build_order:
        feat = features.get(fid, {})
        ftype = feat.get("type", "unknown")
        parent = feat.get("parent")
        placement = feat.get("placement", {})
        notes = feat.get("notes", "")
        params = feat.get("params", {})

        if parent is None:
            # Base function
            lines.append(f"def make_{fid}() -> cq.Workplane:")
            lines.append(f'    """{ftype}: {_params_str(params)}')
            lines.append(f'    Position: Ursprung, Z von 0 bis {params.get("z", "H")}')
            lines.append(f'    """')
            lines.append(f"    # TODO: Coder füllt aus")
            lines.append(f"    pass")
        else:
            # Feature function
            face = placement.get("face", ">Z")
            position = placement.get("position", "center")
            selector_point = placement.get("selector_point")

            func_name = _func_name(fid, ftype)
            lines.append(f"def {func_name}(body: cq.Workplane) -> cq.Workplane:")
            lines.append(f'    """{ftype}: {_params_str(params)}')
            lines.append(f'    Parent: {parent}')
            lines.append(f'    Face: {face}, Position: {position}')
            if selector_point:
                lines.append(
                    f'    SelectorPoint: ({selector_point[0]}, '
                    f'{selector_point[1]}, {selector_point[2]})')
            if notes:
                lines.append(f'    Notes: {notes}')
            lines.append(f'    """')
            lines.append(f"    # TODO: Coder füllt aus")
            lines.append(f"    pass")

        lines.append("")

    # === ASSEMBLY ===
    lines.append("# " + "=" * 60)
    lines.append("# ASSEMBLY")
    lines.append("# " + "=" * 60)
    lines.append("")
    lines.append("def assemble() -> cq.Workplane:")
    lines.append(f'    """Baut {description}.')
    lines.append("")
    lines.append("    Build Order:")
    for i, fid in enumerate(build_order, 1):
        feat = features.get(fid, {})
        ftype = feat.get("type", "")
        parent = feat.get("parent")
        phase = _get_phase(fid, feat, build_order, features)
        lines.append(f"    {i}. {fid} ({ftype}) — {phase}")
    lines.append('    """')

    # Generate assembly calls
    for i, fid in enumerate(build_order):
        feat = features.get(fid, {})
        ftype = feat.get("type", "")
        parent = feat.get("parent")
        func_name = f"make_{fid}" if parent is None else _func_name(fid, ftype)

        if parent is None:
            lines.append(f"    result = {func_name}()")
        else:
            lines.append(f"    result = {func_name}(result)")

    lines.append("    return result")
    lines.append("")

    # === EXPORT ===
    lines.append("# " + "=" * 60)
    lines.append("# EXPORT")
    lines.append("# " + "=" * 60)
    lines.append("result = assemble()")
    lines.append("cq.exporters.export(result, OUTPUT_PATH)")
    lines.append("")

    return "\n".join(lines)


def _func_name(fid: str, ftype: str) -> str:
    """Generiert Funktionsnamen basierend auf Feature-Typ."""
    if "hole" in ftype or "pocket" in ftype or "slot" in ftype or "cutout" in ftype:
        return f"drill_{fid}" if "hole" in ftype else f"cut_{fid}"
    elif "fillet" in ftype:
        return f"apply_{fid}"
    elif "chamfer" in ftype:
        return f"apply_{fid}"
    else:
        return f"add_{fid}"


def _params_str(params: dict) -> str:
    """Formatiert Parameter als kurze Beschreibung."""
    parts = []
    if "x" in params and "y" in params and "z" in params:
        parts.append(f"{params['x']}×{params['y']}×{params['z']}mm")
    if "diameter" in params:
        parts.append(f"∅{params['diameter']}mm")
    if "depth" in params:
        d = params["depth"]
        parts.append(f"Tiefe: {'durchgehend' if d is None else f'{d}mm'}")
    if "n_holes" in params:
        parts.append(f"{params['n_holes']} Löcher")
    if "circle_diameter" in params:
        parts.append(f"Teilkreis ∅{params['circle_diameter']}mm")
    if "radius" in params:
        parts.append(f"Radius {params['radius']}mm")
    if "fillet_radius" in params:
        parts.append(f"R={params['fillet_radius']}mm")
    return ", ".join(parts) if parts else "Siehe params"


def _get_phase(fid, feat, build_order, features):
    """Bestimmt die Build-Phase eines Features."""
    parent = feat.get("parent")
    ftype = feat.get("type", "")

    if parent is None:
        return "Phase 1: Basis"

    is_subtractive = any(k in ftype for k in
                         ["hole", "pocket", "slot", "cutout"])
    is_finishing = ftype in ("fillet", "chamfer", "shell")

    if is_finishing:
        return "Phase 5: Finishing"

    if parent == build_order[0]:  # Parent is base
        # Check if any additive features come after this in build_order
        my_idx = build_order.index(fid)
        has_union_after = any(
            not any(k in features.get(later_fid, {}).get("type", "")
                    for k in ["hole", "pocket", "slot", "cutout",
                              "fillet", "chamfer", "shell"])
            and features.get(later_fid, {}).get("parent") is not None
            for later_fid in build_order[my_idx + 1:]
        )
        if is_subtractive:
            return "Phase 2: Subtraktiv auf Basis (VOR Union)"
        else:
            return "Phase 3: Additiv (Union)"
    else:
        if is_subtractive:
            return "Phase 4: Subtraktiv auf Feature (NACH Union)"
        else:
            return "Phase 3: Additiv (Union)"
