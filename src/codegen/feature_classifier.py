"""
src/codegen/feature_classifier.py — Classify features as standard (template) or complex (LLM).

Standard features have deterministic CadQuery patterns that can be generated
from parameters alone. Complex features need LLM creativity (splines, lofts,
custom shapes).
"""

STANDARD_TYPES: set[str] = {
    # Root bodies
    "box", "base_plate", "base_cylinder", "base_sphere",
    "cylinder", "sphere",
    # Add-operations (union)
    "extrusion_rect", "extrusion_round", "step",
    # Holes
    "hole", "hole_single", "hole_counterbore", "hole_countersink",
    "hole_pattern_grid", "hole_pattern_circular", "hole_pattern_linear",
    # Slots & pockets
    "slot", "groove", "pocket_rect", "cutout",
    # Modifiers
    "fillet", "chamfer", "shell",
}

COMPLEX_TYPES: set[str] = {
    "angled_extrusion",
    "arc_cut", "triangle_cut",
    "custom_shape_cut", "custom_shape_add",
    "loft", "sweep", "spline", "revolution",
}


def is_standard(feature_type: str) -> bool:
    """Check if a feature type can be handled by deterministic templates."""
    return feature_type.lower() in STANDARD_TYPES


def is_complex(feature_type: str) -> bool:
    """Check if a feature type requires LLM code generation."""
    return feature_type.lower() in COMPLEX_TYPES


def classify_blueprint(blueprint: dict) -> str:
    """Classify a full blueprint as 'template', 'llm', or 'mixed'.

    Returns:
        'template' — all features are standard, no LLM needed
        'llm'      — all features are complex, full LLM generation
        'mixed'    — some standard, some complex
    """
    features = blueprint.get("features", {})
    if not features:
        return "template"

    has_standard = False
    has_complex = False

    for fid, feat in features.items():
        ftype = feat.get("type", "") if isinstance(feat, dict) else ""
        if is_standard(ftype):
            has_standard = True
        else:
            has_complex = True

    if has_standard and not has_complex:
        return "template"
    elif has_complex and not has_standard:
        return "llm"
    else:
        return "mixed"


def get_complex_features(blueprint: dict) -> list[str]:
    """Return list of feature IDs that need LLM code generation."""
    features = blueprint.get("features", {})
    return [
        fid for fid, feat in features.items()
        if isinstance(feat, dict) and not is_standard(feat.get("type", ""))
    ]
