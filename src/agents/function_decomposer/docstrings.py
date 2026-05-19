"""Builds the per-feature docstring placed inside each generated function."""

from src.graph.feature_tree import FeatureEntry

from .naming import detect_slot_axis, prefix_for

_SLOT_TYPES = ("slot", "groove")


def make_docstring(feature: FeatureEntry, *, needs_ntp: bool = False) -> str:
    """Build an informative docstring from feature metadata."""
    prefix = prefix_for(feature.id)
    lines = ['    """', f"    Type: {feature.type}"]

    if feature.params:
        lines.append("    Params: " + ", ".join(f"{k}={v}" for k, v in feature.params.items()))

    if feature.parent:
        lines.append(f"    Parent: {feature.parent}")

    if feature.placement:
        lines.append(f"    Placement: {_format_placement(feature.placement)}")
        # Hint: tell Coder which pre-computed constants to use for offsets
        lines.append(f"    ★ Use {prefix}_OFFSET_X / {prefix}_OFFSET_Y for .center() call")
    elif feature.position:
        lines.append(f"    Position: {feature.position}")

    lines.append(f"    Operation: {feature.operation}")

    if feature.type.lower() in _SLOT_TYPES:
        lines.extend(_slot_hint_lines(feature, prefix))

    if needs_ntp:
        lines.extend(_ntp_hint_lines(feature, prefix))

    if feature.notes:
        lines.append(f"    Notes: {feature.notes}")

    lines.append('    """')
    return "\n".join(lines)


def _format_placement(pl) -> str:
    parts = [f"face={pl.face}"]
    if pl.alignment:
        parts.append(f"alignment={pl.alignment}")
    if pl.z_position:
        parts.append(f"z={pl.z_position}")
    parts.append(f"pos={pl.position}")
    return ", ".join(parts)


def _slot_hint_lines(feature: FeatureEntry, prefix: str) -> list[str]:
    axis = detect_slot_axis(feature)
    if axis == "Y":
        rect = f".rect({prefix}_WIDTH, {prefix}_LENGTH).cutBlind(-{prefix}_DEPTH)"
        return [
            f"    ★ NUT entlang Y-Achse → {rect}",
            "    ★ KEIN slot2D! rect() macht rechteckige Nut ohne Rundungen",
        ]
    rect = f".rect({prefix}_LENGTH, {prefix}_WIDTH).cutBlind(-{prefix}_DEPTH)"
    return [
        f"    ★ NUT entlang X-Achse → {rect}",
        "    ★ KEIN slot2D! rect() macht rechteckige Nut ohne Rundungen",
    ]


def _ntp_hint_lines(feature: FeatureEntry, prefix: str) -> list[str]:
    face = feature.placement.face if feature.placement else ">Z"
    return [
        "    ★★ AFTER UNION — use NearestToPointSelector for face selection:",
        f"    body.faces(NearestToPointSelector({prefix}_SELECTOR_POINT))",
        "    .workplane(centerOption='CenterOfBoundBox')",
        f'    Do NOT use body.faces("{face}") — it picks the WRONG face after union!',
    ]
