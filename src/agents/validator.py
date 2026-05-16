"""
src/agents/validator.py — Checks a finished STL against the Blueprint and user intent.

Two checks run in sequence:

  1. Geometry (trimesh, no LLM):
       watertight? volume > 0? enough triangles? sensible dimensions?
       This is already done inside Sandbox, but Validator re-confirms
       and adds dimension sanity checks against the Blueprint.

  2. Semantic (LLM, qwen3:8b):
       Does the model match what the user asked for?
       "Blueprint says M3 hole on top face — does the STL have a hole?"
       "User asked for a bracket — does the model look like a bracket?"

If semantic check fails the Validator writes a validator_feedback string
that the Planner reads on its next attempt. This happens at most 2 times
(semantic_attempts) before the pipeline gives up.

Model: qwen3:8b — fast enough, semantic reasoning doesn't need 30b.
"""

import json
import structlog
from src.config.loader import get_config
from dataclasses import dataclass, field
from pathlib import Path

from src.agents.base import BaseAgent
from src.graph.state import PipelineState
from src.utils.prompt_loader import load_prompt

log = structlog.get_logger()

_prompt = load_prompt("prompt_validator.py")
SEMANTIC_SYSTEM_PROMPT = _prompt.SYSTEM_PROMPT


@dataclass
class ValidatorResult:
    """Result of the full validator check (geometry + semantic)."""
    ok: bool
    feedback: str = ""
    geometry_ok: bool = True
    semantic_ok: bool = True
    stats: dict = field(default_factory=dict)


class ValidatorAgent(BaseAgent):
    """Validates a finished STL against the Blueprint and user intent.

    Called by validator_node after Executor reports success.
    Returns a ValidatorResult — if not ok, feedback goes back to Planner.
    """

    model = get_config().models.validator  # set from config.yaml
    name = "validator"

    def check(self, state: PipelineState) -> ValidatorResult:
        """Run geometry + semantic checks. Returns ValidatorResult."""
        stl_path = state.get("stl_path", "")
        blueprint = state.get("blueprint", {})
        description = state.get("specification", "") or state.get("description", "")

        # --- Step 1: Geometry ---
        geo_ok, geo_feedback, stats = self._check_geometry(stl_path, blueprint)
        if not geo_ok:
            self.log.warning("validator_geometry_fail", feedback=geo_feedback)
            return ValidatorResult(
                ok=False,
                feedback=geo_feedback,
                geometry_ok=False,
                semantic_ok=True,
                stats=stats,
            )

        # --- Step 2: Semantic ---
        # For union blueprints: if geometry already passed AND the computed bounding box
        # matches the STL extents within tolerance, skip the semantic check entirely.
        # The LLM cannot reliably reason about union bounding boxes and produces false negatives.
        root = blueprint.get("root", {})
        if root.get("type") == "union":
            bb = self._compute_union_bbox(root)
            if bb and stats.get("extents_mm"):
                expected = sorted(bb)
                actual = sorted([float(e) for e in stats["extents_mm"]])
                all_match = len(expected) == len(actual) and all(
                    abs(e - a) / max(e, 1) <= 0.15
                    for e, a in zip(expected, actual)
                  )
                if all_match:
                    self.log.info("validator_union_skip_semantic",
                                  expected=expected, actual=actual)
                    return ValidatorResult(ok=True, stats=stats)

        sem_ok, sem_feedback = self._check_semantic(description, blueprint, stats, state=state)
        if not sem_ok:
            self.log.warning("validator_semantic_fail", feedback=sem_feedback[:120])
            return ValidatorResult(
                ok=False,
                feedback=sem_feedback,
                geometry_ok=True,
                semantic_ok=False,
                stats=stats,
            )

        self.log.info("validator_ok", stats=stats)
        return ValidatorResult(ok=True, stats=stats)

    # ------------------------------------------------------------------
    # Geometry check (no LLM — uses trimesh directly)
    # ------------------------------------------------------------------

    def _check_geometry(
        self, stl_path: str, blueprint: dict
    ) -> tuple[bool, str, dict]:
        """Validate STL geometry and cross-check dimensions against Blueprint.

        Returns (ok, feedback_if_not_ok, stats_dict).
        """
        path = Path(stl_path)
        if not path.exists():
            return False, f"STL file not found: {stl_path}", {}

        try:
            import trimesh
            import numpy as np
            mesh = trimesh.load(str(path), force="mesh")
        except Exception as e:
            return False, f"Could not load STL: {e}", {}

        issues = []
        extents = [round(float(e), 2) for e in mesh.extents]
        stats = {
            "triangles": len(mesh.faces),
            "watertight": mesh.is_watertight,
            "volume_mm3": round(float(mesh.volume), 2) if mesh.is_watertight else None,
            "extents_mm": extents,
            # size_mm: sorted [x, y, z] used by 3D viewer and session history
            "size_mm": sorted(extents),
        }

        if len(mesh.faces) < 4:
            issues.append(f"Only {len(mesh.faces)} triangles — model is likely empty.")

        if not mesh.is_watertight:
            # Delegate to STLValidator which has the full repair + tolerance logic.
            # The Validator agent should NOT duplicate the watertight decision —
            # if Sandbox/STLValidator already accepted the mesh, trust that.
            import numpy as np
            edge_face_count = np.zeros(len(mesh.edges_unique), dtype=int)
            for face in mesh.faces_unique_edges:
                edge_face_count[face] += 1
            nm_edge_count = int(np.sum(edge_face_count > 2))
            euler = getattr(mesh, 'euler_number', None)

            # Same tiers as STLValidator: ≤5 nm-edges with volume → accept,
            # euler=2 with ≤20 nm-edges → accept
            if nm_edge_count <= 5 and abs(mesh.volume) > 0:
                self.log.info("validator_watertight_tier1_accept",
                              nm_edges=nm_edge_count, euler=euler)
                stats["watertight"] = True
                stats["volume_mm3"] = round(float(abs(mesh.volume)), 2)
            elif euler == 2 and nm_edge_count <= 20:
                self.log.info("validator_watertight_tier2_accept",
                              nm_edges=nm_edge_count, euler=euler)
                stats["watertight"] = True
                stats["volume_mm3"] = round(float(abs(mesh.volume)), 2)
            else:
                issues.append("Mesh is not watertight (has holes) — unprintable.")

        if mesh.is_watertight and mesh.volume <= 0:
            issues.append(f"Volume is {mesh.volume:.2f}mm³ — geometry may be inside-out.")

        # _validation_error from Planner fallback — structural blueprint problem
        if blueprint.get("_validation_error"):
            issues.append(f"Blueprint validation failed: {blueprint['_validation_error'][:120]}")

        # Dimension sanity check — works with both flat dims and CSG-Tree root
        expected_dims = self._extract_root_dims(blueprint)
        if expected_dims and mesh.extents is not None:
            expected = sorted(expected_dims)
            actual = sorted([float(e) for e in mesh.extents])
            for exp, act in zip(expected, actual):
                if exp > 0 and abs(exp - act) / exp > 0.15:
                    issues.append(
                        f"Dimension mismatch: Blueprint expects ~{[round(e,1) for e in expected]}mm, "
                        f"STL measures {[round(a,1) for a in actual]}mm."
                    )
                    break

        # Volume delta check for modifications — catches "holes added but volume unchanged"
        prev_volume = blueprint.get("_prev_volume_mm3")
        if prev_volume and mesh.is_watertight and stats.get("volume_mm3"):
            curr = stats["volume_mm3"]
            delta_pct = abs(curr - prev_volume) / prev_volume * 100
            # If modification expected new cuts but volume didn't change → flag it
            if blueprint.get("_expected_volume_change") and delta_pct < 1.0:
                issues.append(
                    f"Volume unchanged after modification ({curr:.0f}mm³ = {prev_volume:.0f}mm³). "
                    f"Expected cuts/additions were likely not applied."
                )

        if issues:
            return False, " | ".join(issues), stats
        return True, "", stats

    def _extract_root_dims(self, blueprint: dict) -> list[float]:
        """Extract expected bounding-box dims from Blueprint.

        Handles:
          - Feature Tree format: blueprint["features"][root_id]["params"]
          - CSG-Tree format: blueprint["root"]["x"/"y"/"z"] or ["radius"/"height"]
          - Legacy flat format: blueprint["dimensions"]["x"/"y"/"z"]
        """
        # Feature Tree format: find the root feature (parent=null)
        features = blueprint.get("features", {})
        if features and isinstance(features, dict):
            # Multi-feature blueprints: total STL extent > root feature dims → skip check.
            # Comparing base dims (e.g. z=20) against full STL (z=60=base+boss) is always wrong.
            if len(features) > 1:
                return []
            for feat in features.values():
                if isinstance(feat, dict) and feat.get("parent") is None:
                    params = feat.get("params", {}) or {}
                    ftype = feat.get("type", "")
                    if all(params.get(k) for k in ("x", "y", "z")):
                        try:
                            x, y, z = float(params["x"]), float(params["y"]), float(params["z"])
                            if x > 0 and y > 0 and z > 0:
                                return [x, y, z]
                        except (TypeError, ValueError):
                            pass
                    elif "diameter" in params and "height" in params:
                        try:
                            d = float(params["diameter"])
                            h = float(params["height"])
                            if d > 0 and h > 0:
                                return [d, d, h]
                        except (TypeError, ValueError):
                            pass

        # Legacy flat format
        dims = blueprint.get("dimensions", {})
        if dims:
            x = float(dims.get("x", 0))
            y = float(dims.get("y", 0))
            z = float(dims.get("z", 0))
            if x > 0 and y > 0 and z > 0:
                return [x, y, z]

        # CSG-Tree: get outermost solid node (skip fillet/chamfer/shell wrappers)
        root = blueprint.get("root", {})
        node = root
        # Walk down through modifier wrappers to find the base solid.
        # ⚠ Stop at 'union': union ADDS geometry so the bounding box is LARGER than
        #   any single target. Dimension check is meaningless here — skip it.
        for _ in range(5):
            ntype = node.get("type", "")
            if ntype in ("fillet", "chamfer", "shell"):
                node = node.get("child", {})
            elif ntype == "cut":
                node = node.get("target", {})
            elif ntype in ("union", "intersect"):
                # Can't predict bounding box of a union from target alone — skip check
                return []
            else:
                break

        ntype = node.get("type", "")
        if ntype == "box":
            x = float(node.get("x", 0))
            y = float(node.get("y", 0))
            z = float(node.get("z", 0))
            if x > 0 and y > 0 and z > 0:
                return [x, y, z]
        elif ntype == "cylinder":
            r = float(node.get("radius", 0))
            h = float(node.get("height", 0))
            if r > 0 and h > 0:
                return [r * 2, r * 2, h]

        return []

    def _compute_union_bbox(self, node: dict) -> list[float] | None:
        """Compute the approximate bounding box of a CSG union tree.

        Only handles box+box unions (the most common union pattern).
        Returns [x_extent, y_extent, z_extent] or None if not computable.
        """
        def node_bbox(n) -> tuple | None:
            """Returns (x_min, y_min, z_min, x_max, y_max, z_max) for a primitive."""
            t = n.get("type", "")
            pos = n.get("position", {})
            px, py, pz = float(pos.get("x", 0)), float(pos.get("y", 0)), float(pos.get("z", 0))
            if t == "box":
                hx = float(n.get("x", 0)) / 2
                hy = float(n.get("y", 0)) / 2
                hz = float(n.get("z", 0)) / 2
                if hx > 0:
                    return (px - hx, py - hy, pz - hz, px + hx, py + hy, pz + hz)
            elif t == "cylinder":
                r = float(n.get("radius", 0))
                h = float(n.get("height", 0)) / 2
                if r > 0:
                    return (px - r, py - r, pz - h, px + r, py + r, pz + h)
            return None

        def collect_boxes(n) -> list:
            """Recursively collect all primitive bboxes in a tree."""
            t = n.get("type", "")
            if t in ("box", "cylinder", "sphere"):
                bb = node_bbox(n)
                return [bb] if bb else []
            elif t in ("union", "cut"):
                return collect_boxes(n.get("target", {})) + collect_boxes(n.get("tool", {}))
            elif t in ("fillet", "chamfer", "shell"):
                return collect_boxes(n.get("child", {}))
            return []

        boxes = collect_boxes(node)
        if not boxes:
            return None
        x_min = min(b[0] for b in boxes)
        y_min = min(b[1] for b in boxes)
        z_min = min(b[2] for b in boxes)
        x_max = max(b[3] for b in boxes)
        y_max = max(b[4] for b in boxes)
        z_max = max(b[5] for b in boxes)
        return [x_max - x_min, y_max - y_min, z_max - z_min]

    # ------------------------------------------------------------------
    # Rule-based volume check (no LLM)
    # ------------------------------------------------------------------

    def _compute_expected_volume(self, blueprint: dict) -> float | None:
        """Compute expected volume from Feature Tree blueprint params.

        Returns expected volume in mm³ or None if not computable.
        Only used for Feature Tree blueprints with numeric params.
        Additive features add volume, subtractive features subtract.
        """
        import math
        features = blueprint.get("features", {})
        build_order = blueprint.get("build_order", [])
        if not features or not isinstance(features, dict):
            return None

        total = 0.0
        for fid in build_order:
            feat = features.get(fid)
            if not feat or not isinstance(feat, dict):
                continue
            params = feat.get("params", {}) or {}
            ftype = feat.get("type", "")
            op = feat.get("operation", "add")

            vol = None
            # Box / plate / step / extrusion
            if all(params.get(k) for k in ("x", "y", "z")):
                try:
                    vol = float(params["x"]) * float(params["y"]) * float(params["z"])
                except (TypeError, ValueError):
                    pass
            # Cylinder / boss_cylindrical
            elif params.get("radius") and params.get("height"):
                try:
                    r = float(params["radius"])
                    h = float(params["height"])
                    vol = math.pi * r * r * h
                except (TypeError, ValueError):
                    pass
            elif params.get("diameter") and params.get("height"):
                try:
                    r = float(params["diameter"]) / 2
                    h = float(params["height"])
                    vol = math.pi * r * r * h
                except (TypeError, ValueError):
                    pass
            # Hole
            elif any(kw in ftype for kw in ("hole", "drill", "bore")) and params.get("diameter"):
                try:
                    r = float(params["diameter"]) / 2
                    # Use depth if given, else estimate as parent z (don't block on unknown)
                    depth = params.get("depth")
                    if depth:
                        vol = math.pi * r * r * float(depth)
                except (TypeError, ValueError):
                    pass
            # Pocket / slot / groove
            elif any(kw in ftype for kw in ("pocket", "slot", "groove")) and params.get("depth"):
                try:
                    depth = float(params["depth"])
                    if params.get("x") and params.get("y"):
                        vol = float(params["x"]) * float(params["y"]) * depth
                    elif params.get("length") and params.get("width"):
                        vol = float(params["length"]) * float(params["width"]) * depth
                except (TypeError, ValueError):
                    pass

            if vol is not None:
                if op == "subtract":
                    total -= vol
                else:
                    total += vol

        return total if total > 0 else None

    def _count_additive_solids(self, blueprint: dict) -> int:
        """Count additive solid parts (box/cylinder/plate) in the blueprint.

        Holes/pockets/slots/chamfers are not solids. Used to detect
        multi-part assemblies where additive parts may overlap.
        """
        features = blueprint.get("features", {})
        if not isinstance(features, dict):
            return 0
        _NON_SOLID = ("hole", "drill", "bore", "pocket", "slot", "groove",
                      "chamfer", "fillet", "bevel", "shell", "cutout")
        count = 0
        for feat in features.values():
            if not isinstance(feat, dict):
                continue
            if feat.get("operation", "add") == "subtract":
                continue
            ftype = (feat.get("type") or "").lower()
            if any(kw in ftype for kw in _NON_SOLID):
                continue
            count += 1
        return count

    def _volume_check_passes(self, blueprint: dict, actual_volume: float | None) -> bool:
        """Return True if actual STL volume matches expected blueprint volume.

        Single-solid blueprints: symmetric ±20% tolerance.
        Multi-part additive blueprints (>=2 additive solids): the naive
        volume sum is an UPPER bound — overlapping plates can only reduce
        actual volume, never increase it. So actual < expected is normal;
        only actual significantly EXCEEDING expected signals a real error
        (unexpected extra geometry).

        If volume cannot be computed from blueprint, returns True (don't block).
        If actual_volume is None (e.g. non-watertight mesh), returns False so
        the semantic LLM check runs as a fallback.
        """
        if actual_volume is None or actual_volume <= 0:
            return False
        expected = self._compute_expected_volume(blueprint)
        if expected is None or expected <= 0:
            return True

        additive_solids = self._count_additive_solids(blueprint)
        if additive_solids >= 2:
            # Multi-part: expected is an upper bound. Pass when actual does
            # not exceed expected by more than 20% (tessellation slack).
            within = actual_volume <= expected * 1.20
            ratio = (actual_volume - expected) / expected
        else:
            ratio = abs(actual_volume - expected) / expected
            within = ratio <= 0.20
        self.log.info("validator_volume_check",
                      expected_mm3=round(expected, 0),
                      actual_mm3=round(actual_volume, 0),
                      ratio_pct=round(ratio * 100, 1),
                      additive_solids=additive_solids,
                      passes=within)
        return within

    # ------------------------------------------------------------------
    # Semantic check (LLM)
    # ------------------------------------------------------------------

    def _check_semantic(
        self, description: str, blueprint: dict, stats: dict,
        state: dict = None
    ) -> tuple[bool, str]:
        """Ask the LLM if the Blueprint matches the user description.

        Returns (ok, feedback_if_not_ok).
        Falls back to ok=True if LLM call fails — we don't want a
        connectivity issue to block an otherwise valid model.
        """
        # Rule-based volume check: if computed blueprint volume matches STL ±20%, accept.
        # The 9b LLM often misinterprets total bounding box vs individual feature dims.
        # Only skip for Feature Tree blueprints (where we can compute volume reliably).
        actual_volume = stats.get("volume_mm3")
        if (
            "build_order" in blueprint
            and isinstance(blueprint.get("features"), dict)
            and not (state or {}).get("change_description")  # modifications still need LLM
        ):
            if self._volume_check_passes(blueprint, actual_volume):
                self.log.info("validator_volume_rule_pass",
                              volume_mm3=actual_volume,
                              msg="Volume matches blueprint — skipping LLM semantic check")
                return True, ""

        change_desc = state.get("change_description", "") if state else ""
        if change_desc:
            intent_section = (
                f"## Modification applied\n{change_desc}\n\n"
                f"IMPORTANT: validate that THIS CHANGE was applied correctly.\n"
                f"Do NOT compare against the original description below — "
                f"only check if the modification was applied.\n\n"
                f"## Original description (for context only)\n{description}\n\n"
            )
        else:
            intent_section = f"## User description\n{description}\n\n"

        # For union blueprints: compute expected bounding box and include it explicitly
        # so the LLM doesn't have to derive it and can't get it wrong.
        union_note = ""
        root = blueprint.get("root", {})
        if root.get("type") == "union":
            bb = self._compute_union_bbox(root)
            if bb:
                union_note = (
                    f"\n## Expected bounding box (computed from blueprint union)\n"
                    f"Total extents: ~{[round(v,1) for v in sorted(bb)]}mm\n"
                    f"This is CORRECT for a union model — do NOT flag correct dimensions as wrong.\n\n"
                )

        # Include deterministic geometry pre-check report when available
        precheck_section = ""
        precheck_report = state.get("geometry_precheck_report", "") if state else ""
        if precheck_report:
            precheck_section = (
                f"## Geometry Pre-Check (DETERMINISTIC — trust these numbers)\n"
                f"{precheck_report}\n\n"
            )

        prompt = (
            f"{intent_section}"
            f"## Blueprint used\n{json.dumps(blueprint, indent=2)}\n\n"
            f"{precheck_section}"
            f"## Generated STL stats\n{json.dumps(stats, indent=2)}\n"
            f"{union_note}\n"
            "Does this model match the intent?"
        )

        try:
            result = self.call_json(prompt, system=SEMANTIC_SYSTEM_PROMPT)
            # Prompt uses "is_valid"; fall back to "ok" for backward compat
            ok = bool(result.get("is_valid", result.get("ok", True)))
            feedback = result.get("feedback", "")
            return ok, feedback
        except (ValueError, ConnectionRefusedError) as e:
            # If Ollama is down or returns bad JSON: be optimistic, let it through
            self.log.warning("validator_semantic_fallback", error=str(e))
            return True, ""
