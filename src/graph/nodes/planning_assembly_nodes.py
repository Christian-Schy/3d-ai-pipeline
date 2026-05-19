"""Planning node subset split out from planning_nodes.py."""
from __future__ import annotations

import json
import re
import time

import structlog

from src.graph.state import PipelineState

from ._tracing import _make_trace

log = structlog.get_logger()

def assembly_node(state: PipelineState) -> dict:
    """Step 3: Assemble parts into a complete semantic blueprint.

    Deterministic: TeilDefinierer already attached parent + position + orientation
    via the PositionNormalizer. This step just merges everything into the final
    blueprint format. No LLM call needed.
    """
    teil_defs = state.get("teil_definitionen", [])
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1

    if not teil_defs:
        log.warning("node_assembly_skipped", reason="no_teil_definitionen")
        return {"agent_traces": [_make_trace(
            agent="assembly", step=_step,
            input_data={}, output_data={"skipped": True},
            start_time=_t0,
        )]}

    # Single-part shortcut
    if len(teil_defs) == 1:
        blueprint = _single_part_blueprint(teil_defs[0])
        log.info("node_assembly_single_part", features=len(blueprint.get("features", {})))
        _trace = _make_trace(
            agent="assembly", step=_step,
            input_data={"teil_count": 1},
            output_data={"features": len(blueprint.get("features", {})), "mode": "single_part_shortcut"},
            start_time=_t0,
        )
        return {
            "blueprint": blueprint,
            "plan_valid": False,
            "plan_validation_issues": "",
            "coordinate_validation_issues": "",
            "validator_feedback": "",
            "agent_traces": [_trace],
        }

    # Multi-part: deterministic assembly from teil_defs (each has parent + position)
    blueprint = _deterministic_assembly(teil_defs)

    log.info("node_assembly_done_deterministic",
             features=len(blueprint.get("features", {})),
             build_order=blueprint.get("build_order", []))

    _trace = _make_trace(
        agent="assembly", step=_step,
        input_data={"teil_count": len(teil_defs)},
        output_data={
            "features": len(blueprint.get("features", {})),
            "build_order": blueprint.get("build_order", []),
            "mode": "deterministic",
        },
        start_time=_t0,
    )

    return {
        "blueprint": blueprint,
        "plan_valid": False,
        "plan_validation_issues": "",
        "coordinate_validation_issues": "",
        "validator_feedback": "",
        "agent_traces": [_trace],
    }


def _deterministic_assembly(teil_defs: list[dict]) -> dict:
    """Merge teil_definitions into a complete semantic blueprint.

    Each teil_def already has parent + position + orientation (from
    PositionNormalizer + build_position + build_orientation). This function
    just combines all teile and their features into one features dict with
    proper build_order.

    No LLM needed — purely structural merging.
    """
    features = {}
    build_order = []

    # First pass: add all teile (root first, then others)
    roots = [t for t in teil_defs if t.get("parent") is None]
    children = [t for t in teil_defs if t.get("parent") is not None]

    # Topological ordering: parent before child
    ordered_teile = list(roots)
    remaining = list(children)
    while remaining:
        added_any = False
        for t in list(remaining):
            parent_id = t.get("parent")
            if parent_id in {o["id"] for o in ordered_teile}:
                ordered_teile.append(t)
                remaining.remove(t)
                added_any = True
        if not added_any:
            # Circular or orphaned — just append the rest to avoid infinite loop
            ordered_teile.extend(remaining)
            break

    # Build features dict + build_order
    for teil_def in ordered_teile:
        teil_id = teil_def["id"]
        is_root = teil_def.get("parent") is None

        # Add teil itself
        teil_feature = {
            "type": teil_def.get("type", "box"),
            "params": teil_def.get("params", {}),
            "orientation": teil_def.get("orientation", "standard"),
            "parent": teil_def.get("parent"),
            "operation": "add",
            "notes": "",
        }
        if not is_root and teil_def.get("position"):
            teil_feature["position"] = teil_def["position"]

        features[teil_id] = teil_feature
        build_order.append(teil_id)

        # Add this teil's features (expanded for multi-axis slots)
        expanded = _expand_multi_axis_slots(teil_def.get("features", []))
        for feat in expanded:
            feat_id = feat.get("id", f"feat_{teil_id}_{len(features)}")
            # Deduplicate: if another teil already used this id, prefix with parent
            if feat_id in features:
                feat_id = f"{teil_id}_{feat_id}"
            pos = feat.get("position", {
                "side": "oben", "alignment": "centered",
                "edge_distances": None, "angle_deg": 0, "notes": "",
            })
            # Merge feature-level notes into position.notes if position.notes is empty
            if not pos.get("notes") and feat.get("notes"):
                pos["notes"] = feat["notes"]
            features[feat_id] = {
                "type": feat.get("type", "hole_single"),
                "params": feat.get("params", {}),
                "parent": teil_id,
                "position": pos,
                "operation": feat.get("operation", "subtract"),
                "notes": feat.get("notes", ""),
            }
            build_order.append(feat_id)

    # Build description from teil_defs
    teil_names = [t["id"] for t in teil_defs]
    description = f"Baugruppe aus {len(teil_defs)} Teilen: {', '.join(teil_names)}"

    return {
        "description": description,
        "build_order": build_order,
        "features": features,
    }


def _expand_multi_axis_slots(features: list[dict]) -> list[dict]:
    """Split slot features with combined axis notes into separate features.

    "entlang X und Y" → two slots, one "entlang X" and one "entlang Y".
    This handles cases where the LLM merges two slots into one feature.
    """
    expanded = []
    for feat in features:
        notes = (feat.get("position") or {}).get("notes", "")
        notes_lower = notes.lower()
        ftype = feat.get("type", "")

        # Detect any two-axis combination: "X und Y", "Y und Z", "X und Z", etc.
        axis_match = re.findall(r"([xyz])", notes_lower)
        if ftype in ("slot", "groove") and len(axis_match) >= 2 and "und" in notes_lower:
            axes = [a.upper() for a in dict.fromkeys(axis_match)]  # unique, ordered
            for axis_label in axes:
                clone = json.loads(json.dumps(feat))  # deep copy
                clone["id"] = f"{feat.get('id', 'slot')}_{axis_label.lower()}"
                clone["position"]["notes"] = f"entlang {axis_label}"
                expanded.append(clone)
            log.info("expand_multi_axis_slot", original_id=feat.get("id"), split_into=len(axes))
        else:
            expanded.append(feat)

    # Fix perpendicular axis references: when two slots on the same face both
    # map to the same direction (because one axis is perpendicular to the face),
    # remap to the two actual on-face directions.
    expanded = _fix_slot_axis_per_face(expanded)

    return expanded


# Which global axes are visible on each face, and which is perpendicular
_FACE_AXES = {
    "oben":   ("X", "Y", "Z"),  # visible: X, Y; perp: Z
    "unten":  ("X", "Y", "Z"),
    "rechts": ("Y", "Z", "X"),  # visible: Y, Z; perp: X
    "links":  ("Y", "Z", "X"),
    "vorne":  ("X", "Z", "Y"),  # visible: X, Z; perp: Y
    "hinten": ("X", "Z", "Y"),
}


def _fix_slot_axis_per_face(features: list[dict]) -> list[dict]:
    """Fix axis notes on slots where the stated axis is perpendicular to the face.

    On face "rechts" (>X), the visible axes are Y and Z. If the LLM writes
    "entlang X" and "entlang Y", X is perpendicular and would be a duplicate.
    This function remaps the perpendicular axis to the other visible axis.
    """

    # Group slots by face (side)
    slots_by_side: dict[str, list[int]] = {}
    for i, feat in enumerate(features):
        if feat.get("type") not in ("slot", "groove"):
            continue
        side = (feat.get("position") or {}).get("side", "oben")
        slots_by_side.setdefault(side, []).append(i)

    for side, indices in slots_by_side.items():
        if side not in _FACE_AXES:
            continue
        axis1, axis2, perp = _FACE_AXES[side]

        for idx in indices:
            notes = (features[idx].get("position") or {}).get("notes", "")
            notes_lower = notes.lower()
            # Check if this slot references the perpendicular axis
            if f"entlang {perp.lower()}" in notes_lower or f"{perp.lower()}-achse" in notes_lower:
                # Determine which visible axis is NOT yet used by other slots on this face
                used_axes = set()
                for other_idx in indices:
                    if other_idx == idx:
                        continue
                    other_notes = (features[other_idx].get("position") or {}).get("notes", "").lower()
                    if f"entlang {axis1.lower()}" in other_notes or f"{axis1.lower()}-achse" in other_notes:
                        used_axes.add(axis1)
                    if f"entlang {axis2.lower()}" in other_notes or f"{axis2.lower()}-achse" in other_notes:
                        used_axes.add(axis2)

                # Assign the unused visible axis, or axis2 as default
                if axis1 not in used_axes:
                    new_axis = axis1
                elif axis2 not in used_axes:
                    new_axis = axis2
                else:
                    new_axis = axis2  # both used, default to second

                features[idx]["position"]["notes"] = f"entlang {new_axis}"
                log.info("fix_slot_perp_axis",
                         side=side, old=notes, new=f"entlang {new_axis}",
                         reason=f"{perp} is perpendicular to {side}")

    return features


def _single_part_blueprint(teil_def: dict) -> dict:
    """Build a complete blueprint from a single teil definition (no LLM needed)."""
    teil_id = teil_def["id"]
    features = {}

    # Root body
    features[teil_id] = {
        "type": teil_def.get("type", "box"),
        "params": teil_def.get("params", {}),
        "orientation": teil_def.get("orientation", "standard"),
        "parent": None,
        "operation": "add",
        "notes": "",
    }

    # Sub-features (holes, slots, etc.)
    # First expand multi-axis slots ("entlang X und Y" → 2 separate features)
    expanded_features = _expand_multi_axis_slots(teil_def.get("features", []))

    for feat in expanded_features:
        feat_id = feat.get("id", f"feat_{teil_id}")
        pos = feat.get("position", {
            "side": "oben", "alignment": "centered",
            "edge_distances": None, "angle_deg": 0, "notes": "",
        })
        # Merge feature-level notes into position.notes if position.notes is empty
        if not pos.get("notes") and feat.get("notes"):
            pos["notes"] = feat["notes"]
        features[feat_id] = {
            "type": feat.get("type", "hole_single"),
            "params": feat.get("params", {}),
            "parent": teil_id,
            "position": pos,
            "operation": feat.get("operation", "subtract"),
            "notes": feat.get("notes", ""),
        }

    build_order = [teil_id] + [f.get("id", f"feat_{teil_id}") for f in expanded_features]

    return {
        "description": f"{teil_def.get('type', 'box')} {teil_def.get('params', {})}",
        "build_order": build_order,
        "features": features,
    }
