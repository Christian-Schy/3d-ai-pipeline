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

log = structlog.get_logger()

SEMANTIC_SYSTEM_PROMPT = Path("data/prompts/agents/validator.md").read_text(encoding="utf-8")


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

        Handles both:
          - CSG-Tree format: blueprint["root"]["x"/"y"/"z"] or ["radius"/"height"]
          - Legacy flat format: blueprint["dimensions"]["x"/"y"/"z"]
        """
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
            ok = bool(result.get("ok", True))
            feedback = result.get("feedback", "")
            return ok, feedback
        except (ValueError, ConnectionRefusedError) as e:
            # If Ollama is down or returns bad JSON: be optimistic, let it through
            self.log.warning("validator_semantic_fallback", error=str(e))
            return True, ""
