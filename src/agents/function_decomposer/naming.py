"""Function naming + slot axis detection — pure string helpers."""

from src.graph.feature_tree import FeatureEntry

_HOLE_KEYWORDS = ("hole", "drill", "bore", "cbore", "csk")
_CUT_KEYWORDS = ("slot", "groove", "pocket", "cut")
_FILLET_KEYWORDS = ("fillet", "chamfer")


def prefix_for(fid: str) -> str:
    """Canonical UPPER_SNAKE prefix for a feature id (used for constant names)."""
    return fid.upper().replace("-", "_").replace(" ", "_")


def function_name(feature: FeatureEntry) -> str:
    """Derive a Python function name from feature id and operation."""
    fid = feature.id.replace("-", "_").replace(" ", "_").lower()
    ftype = feature.type.lower()

    if feature.parent is None:
        return f"make_{fid}"

    if feature.operation == "subtract":
        if any(kw in ftype for kw in _HOLE_KEYWORDS):
            return f"drill_{fid}"
        if any(kw in ftype for kw in _CUT_KEYWORDS) or "corner" in ftype:
            return f"cut_{fid}"
        if "text" in ftype:
            return f"engrave_{fid}"
        return f"subtract_{fid}"

    if any(kw in ftype for kw in _FILLET_KEYWORDS):
        return f"apply_{fid}"
    if "shell" in ftype:
        return f"hollow_{fid}"
    if "text" in ftype:
        return f"emboss_{fid}"
    return f"add_{fid}"


def detect_slot_axis(feature: FeatureEntry) -> str:
    """Detect slot/groove axis direction from id/notes. Returns 'X' or 'Y'.

    Defaults to 'Y' (most common for 'Nut entlang ...').
    """
    fid_lower = feature.id.lower()
    if "x_axis" in fid_lower or "_x" in fid_lower or "along_x" in fid_lower:
        return "X"
    if "y_axis" in fid_lower or "_y" in fid_lower or "along_y" in fid_lower:
        return "Y"

    notes = ""
    if feature.placement and feature.placement.notes:
        notes = feature.placement.notes.lower()
    if feature.notes:
        notes += " " + feature.notes.lower()

    if "entlang x" in notes or "along x" in notes:
        return "X"
    if "entlang y" in notes or "along y" in notes:
        return "Y"

    return "Y"
