"""
src/graph/blueprint_utils.py — Utility functions for Blueprint manipulation.

Extracted from PlannerAgent._apply_diff() to make it reusable.
"""
import copy
import structlog

log = structlog.get_logger()


def apply_patch(blueprint: dict, diff: dict, change_hint: str = "") -> tuple[dict, int]:
    """Apply a diff returned by the LLM to the existing blueprint.

    The LLM returns {"changes": [{"path": "root.tool.radius", "new_value": 6.0}]}
    We walk the dot-notation path and set the new value.

    Args:
        blueprint:   The current blueprint dict (will not be mutated).
        diff:        The diff dict from the LLM ({"changes": [...], "description": "..."}).
        change_hint: Short description of the change (for fallback description update).

    Returns:
        (updated_blueprint, applied_count)
        applied_count is the number of paths successfully updated.
    """
    result = copy.deepcopy(blueprint)
    changes = diff.get("changes", [])
    applied = 0

    for change in changes:
        path = change.get("path", "")
        new_value = change.get("new_value")
        if not path or new_value is None:
            continue

        # Walk the path and set the value
        keys = path.split(".")
        target = result
        try:
            for key in keys[:-1]:
                target = target[int(key)] if key.isdigit() else target[key]
            last_key = keys[-1]
            if last_key.isdigit():
                target[int(last_key)] = new_value
            else:
                target[last_key] = new_value
            applied += 1
            log.info("blueprint_patch_applied", path=path, new_value=new_value)
        except (KeyError, IndexError, TypeError) as e:
            log.warning("blueprint_patch_path_error", path=path, error=str(e))

    # Update description — use LLM suggestion or build from change
    if diff.get("description"):
        result["description"] = diff["description"]
    elif changes:
        # Fallback: append change hint to existing description
        old_desc = result.get("description", "")
        result["description"] = f"{old_desc} (modified: {change_hint})"

    log.info("blueprint_patch_summary",
             changes_requested=len(changes),
             changes_applied=applied)
    return result, applied
