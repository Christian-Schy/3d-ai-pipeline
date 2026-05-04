"""
src/agents/pocket_child_placer.py — Bohrungen-in-Taschen Extraktor.

Laeuft NACH der Assembly, VOR dem Resolver. Schaut sich das fertige
semantische Blueprint an, sucht alle Pocket-Features (subtraktiv,
type=pocket_rect/cutout) und liest aus dem User-Text heraus, ob darin
eine Bohrung sitzen soll.

Der Output sind zusaetzliche SemanticFeatures mit parent=<pocket_id>
und position.depth_reference="pocket_floor". Der Resolver platziert sie
ueber die _resolve_feature_in_feature-Logik im Pocket-Lokalframe.

Trigger-Heuristik (deterministisch, vor LLM-Call):
  - Spec enthaelt "in der tasche" / "in der ausnehmung" / "im pocket"
    / "am taschenboden" / "in der vertiefung" / "in der aushoehlung"
  - Mindestens eine Pocket im Blueprint vorhanden

Wenn weder das eine noch das andere zutrifft: Skip ohne LLM-Call.
"""

from __future__ import annotations

import re
import json as _json
import structlog

from src.agents.base import BaseAgent
from src.config.loader import get_config
from src.utils.prompt_loader import load_prompt

log = structlog.get_logger()

_prompt = load_prompt("prompt_pocket_child_placer.py")
SYSTEM_PROMPT = _prompt.SYSTEM_PROMPT
POCKET_CHILD_PROMPT_TEMPLATE = _prompt.POCKET_CHILD_PROMPT_TEMPLATE
FEW_SHOT_EXAMPLES = _prompt.FEW_SHOT_EXAMPLES


# Trigger-Phrasen — wenn keine davon im Spec, lohnt der LLM-Call nicht
_IN_POCKET_HINTS = re.compile(
    r"\b(?:in\s+der\s+(?:tasche|ausnehmung|aushoehlung|aushöhlung|vertiefung)"
    r"|im\s+pocket"
    r"|am\s+(?:taschenboden|pocketboden)"
    r"|innerhalb\s+der\s+tasche)",
    re.IGNORECASE,
)

# Erkennt die Pocket-Featuretypen die wir als Container unterstuetzen.
_POCKET_TYPES = {"pocket_rect", "pocket_round", "cutout"}


class PocketChildPlacer(BaseAgent):
    """Extracts hole-in-pocket features from the user spec.

    Runs after assembly, before blueprint_resolver. Returns a partial
    state update that injects feature-in-feature entries into the
    blueprint's features dict, with parent set to the matching pocket.
    """

    name = "pocket_child_placer"
    dspy_demo_fields = {
        "input_fields": ["specification", "pockets_listing"],
        "output_field": "pocket_holes",
    }

    def __init__(self):
        cfg = get_config()
        # Same model as the inventar agent — small task, predictable schema.
        self.model = getattr(cfg.models, "pocket_child_placer", cfg.models.inventar)
        super().__init__()
        # Seed few-shot list when no DSPy-optimized demos exist yet.
        if not self._dspy_demos:
            self._dspy_demos = [
                (
                    f"specification: {ex['spec']}\npockets: {_json.dumps(ex['pockets'], ensure_ascii=False)}",
                    _json.dumps(ex["output"], ensure_ascii=False),
                )
                for ex in FEW_SHOT_EXAMPLES
            ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(self, specification: str, blueprint: dict) -> dict:
        """Return a partial blueprint update or {} if skip.

        On success returns:
          {"features_to_add": {fid: feat, ...},
           "feature_ids_to_remove": [fid, ...]}

        Decision tree:
          1. No spec or no blueprint                      → skip
          2. No "in der tasche"-style phrase in spec      → skip
          3. No pocket-typed feature in blueprint         → skip
          4. Otherwise: build a pocket listing, ask LLM,
             validate, and return new SemanticFeature dicts.
             Plus: detect upstream-chain duplicates of the same hole that
             were attached to the part instead of the pocket and mark
             them for removal.
        """
        if not specification or not blueprint:
            return {}

        if not _IN_POCKET_HINTS.search(specification or ""):
            log.debug("pocket_child_skip", reason="no_hint")
            return {}

        pockets = self._collect_pockets(blueprint)
        if not pockets:
            log.debug("pocket_child_skip", reason="no_pockets")
            return {}

        log.info("pocket_child_extracting",
                 pocket_count=len(pockets),
                 spec_len=len(specification))

        try:
            holes = self._call_llm(specification, pockets)
        except Exception as e:
            log.warning("pocket_child_llm_failed", error=str(e)[:120])
            return {}

        validated = self._validate_holes(holes, pockets, blueprint)
        if not validated:
            log.info("pocket_child_no_holes_extracted")
            return {}

        # Find upstream-chain duplicates: holes the inventar/teil_definierer
        # attached to the part because it didn't recognize "in der Tasche"
        # as a feature-parent hint. We match by (parent=part-of-pocket,
        # type, diameter, depth) since the upstream depth is the user-stated
        # depth and our depth_local preserves that value.
        to_remove = self._find_upstream_duplicates(validated, blueprint, pockets)
        if to_remove:
            log.info("pocket_child_dedup",
                     removing=to_remove,
                     for_new_holes=list(validated.keys()))

        log.info("pocket_child_done", added=len(validated), removed=len(to_remove))
        return {
            "features_to_add": validated,
            "feature_ids_to_remove": to_remove,
        }

    @staticmethod
    def _find_upstream_duplicates(
        validated: dict[str, dict],
        blueprint: dict,
        pockets: list[dict],
    ) -> list[str]:
        """Identify hole features that are duplicates of newly-extracted
        pocket children, created by the upstream chain.

        For each new in-pocket hole we look for a sibling on the SAME part
        (the pocket's parent) with matching type, diameter and depth (the
        upstream depth equals the user-stated depth, which we preserved
        as depth_local on the new feature). Only an exact match is removed
        to keep the dedup conservative.
        """
        features = blueprint.get("features") or {}
        pocket_parent_by_id = {p["id"]: p.get("parent_part") for p in pockets}
        # Tally upstream candidates so we don't double-claim a single
        # candidate across multiple new holes.
        claimed: set[str] = set()
        to_remove: list[str] = []

        for new_fid, new_feat in validated.items():
            pocket_id = new_feat.get("parent")
            part_id = pocket_parent_by_id.get(pocket_id)
            if not part_id:
                continue
            new_params = new_feat.get("params") or {}
            new_type = (new_feat.get("type") or "").lower()
            new_diam = _safe_float(new_params.get("diameter"))
            new_depth = _safe_float(new_params.get("depth"))
            if new_diam is None:
                continue

            for fid, feat in features.items():
                if fid in claimed or fid == new_fid:
                    continue
                if not isinstance(feat, dict):
                    continue
                if feat.get("parent") != part_id:
                    continue
                if (feat.get("type") or "").lower() != new_type:
                    continue
                if (feat.get("operation") or "add").lower() != "subtract":
                    continue
                fp = feat.get("params") or {}
                fd = _safe_float(fp.get("diameter"))
                ft = _safe_float(fp.get("depth"))
                if fd is None or new_diam is None:
                    continue
                if abs(fd - new_diam) > 0.01:
                    continue
                # Match upstream depth against the user-stated depth, which
                # we kept as depth_local on the new feature.
                if ft is not None and new_depth is not None and abs(ft - new_depth) > 0.01:
                    continue
                claimed.add(fid)
                to_remove.append(fid)
                break

        return to_remove

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_pockets(blueprint: dict) -> list[dict]:
        """Walk blueprint.features and collect pocket-typed entries.

        Returns dicts with id, parent_part (for context), x/y/depth, and
        a position_hint inferred from the pocket's own placement (if
        already resolved) or its semantic position (alignment/side).
        """
        features = blueprint.get("features", {}) or {}
        if not isinstance(features, dict):
            return []
        out: list[dict] = []
        for fid, feat in features.items():
            if not isinstance(feat, dict):
                continue
            ftype = (feat.get("type") or "").lower()
            if ftype not in _POCKET_TYPES:
                continue
            if (feat.get("operation") or "add").lower() != "subtract":
                continue
            params = feat.get("params", {}) or {}
            position = feat.get("position") or {}
            position_hint = _derive_position_hint(position)
            out.append({
                "id": fid,
                "parent_part": feat.get("parent"),
                "position_hint": position_hint,
                "x": params.get("x"),
                "y": params.get("y"),
                "depth": params.get("depth"),
            })
        return out

    def _call_llm(self, specification: str, pockets: list[dict]) -> list[dict]:
        """Call the LLM and parse the JSON response into a list of hole specs."""
        pockets_listing = _json.dumps(pockets, ensure_ascii=False, indent=2)
        prompt = POCKET_CHILD_PROMPT_TEMPLATE.format(
            specification=specification,
            pockets_listing=pockets_listing,
        )
        result = self.call_json(prompt, system=SYSTEM_PROMPT)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return result.get("pocket_holes", []) or []
        return []

    def _validate_holes(
        self, holes: list[dict], pockets: list[dict], blueprint: dict,
    ) -> dict[str, dict]:
        """Validate LLM output and convert to SemanticFeature-shaped dicts.

        Drops anything that:
          - References an unknown pocket_id
          - Has non-positive diameter / depth
          - Has a non-allowed type (only hole_single supported in MVP)
        """
        valid_pocket_ids = {p["id"] for p in pockets}
        existing_ids = set((blueprint.get("features") or {}).keys())
        out: dict[str, dict] = {}
        for h in holes or []:
            if not isinstance(h, dict):
                continue
            parent_id = h.get("parent_pocket_id") or h.get("parent")
            if parent_id not in valid_pocket_ids:
                log.warning("pocket_child_unknown_parent",
                            parent=parent_id,
                            valid=list(valid_pocket_ids))
                continue
            ftype = (h.get("type") or "hole_single").lower()
            # MVP: only hole_single. Slot-in-pocket etc. is a phase-2 add.
            if ftype != "hole_single":
                log.info("pocket_child_skipping_unsupported_type", type=ftype)
                continue
            params = h.get("params") or {}
            try:
                d = float(params.get("diameter") or 0)
                depth = params.get("depth")
                depth_f = float(depth) if depth is not None else None
            except (TypeError, ValueError):
                continue
            if d <= 0 or (depth_f is not None and depth_f <= 0):
                continue

            fid = h.get("feature_id") or f"hole_in_{parent_id}_{len(out) + 1}"
            # Avoid clobbering an existing feature.
            base_fid = fid
            i = 2
            while fid in existing_ids or fid in out:
                fid = f"{base_fid}_{i}"
                i += 1

            position = h.get("position") or {}
            # Always force pocket_floor for the depth reference — the agent
            # was prompted for it, but we re-enforce in case the LLM omitted it.
            position.setdefault("side", "oben")
            position.setdefault("alignment", "centered")
            position["depth_reference"] = "pocket_floor"

            out[fid] = {
                "id": fid,
                "type": ftype,
                "parent": parent_id,
                "operation": "subtract",
                "orientation": "standard",
                "params": {
                    "diameter": d,
                    "depth": depth_f if depth_f is not None else None,
                },
                "position": position,
                "notes": h.get("source_text", "")[:80],
            }
        return out


def _safe_float(value) -> float | None:
    """float() that returns None on failure or empty input."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _derive_position_hint(position: dict) -> str:
    """Pick a short hint that disambiguates one pocket from another.

    Falls back through alignment → side → empty string.
    """
    if not isinstance(position, dict):
        return ""
    align = (position.get("alignment") or "").lower()
    if "left" in align:
        return "links"
    if "right" in align:
        return "rechts"
    if "top" in align:
        return "oben"
    if "bottom" in align:
        return "unten"
    side = (position.get("side") or "").lower()
    if side and side != "oben":
        return side
    return "zentral"
