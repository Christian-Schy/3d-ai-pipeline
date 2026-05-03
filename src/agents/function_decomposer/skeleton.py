"""Top-level dispatcher: pick sub-assembly vs. linear emission."""

import structlog

from src.graph.feature_tree import FeatureTree

from .grouping import build_assembly_groups
from .skeleton_linear import generate_linear_skeleton
from .skeleton_sub_assembly import generate_sub_assembly_skeleton


_log = structlog.get_logger()


def generate_skeleton(blueprint: dict) -> str:
    """Generate a Python skeleton from a Feature Tree blueprint.

    Uses the **sub-assembly pattern** when at least one root child is an
    additive feature with its own children — that's where face-selection
    after union becomes ambiguous, so building parts standalone helps.

    Falls back to the linear pattern (NearestToPointSelector for face
    disambiguation) otherwise.

    Returns empty string if the blueprint isn't in Feature Tree format.
    """
    if not FeatureTree.is_feature_tree(blueprint):
        return ""

    try:
        ft = FeatureTree.from_dict(blueprint)
    except Exception as e:
        _log.error("function_decomposer_parse_failed", error=str(e))
        return ""

    groups = build_assembly_groups(ft)
    if groups.is_sub_assembly_eligible():
        return generate_sub_assembly_skeleton(ft, groups)
    return generate_linear_skeleton(ft)
