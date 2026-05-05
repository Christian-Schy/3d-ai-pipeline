"""src/agents/pocket_child_placer.py — Bohrungen-zu-Taschen Zuordner.

Laeuft NACH der Assembly, VOR dem Resolver. Schaut sich das fertige
semantische Blueprint an und ordnet bestehende Bohrungs-Features einer
Tasche zu, wenn der User-Text das so beschreibt ("in der Tasche", ...).

Aufgaben-Trennung (V2, ab 2026-05-05):
  - Position parsen: macht der feature_definierer (er kennt center_offset,
    edge_distances, angle_deg).
  - Containment "in welcher Tasche?": macht dieser Agent per LLM.
  - Position uebernehmen: deterministisch — der Code clont das Upstream-
    Feature, aendert nur parent + ID + setzt depth_reference.

Trigger-Heuristik (deterministisch, vor LLM-Call):
  - Spec enthaelt "in der tasche" / "in der ausnehmung" / "im pocket" /
    "am taschenboden" / "in der vertiefung" / "in der aushoehlung"
  - Mindestens eine Pocket im Blueprint vorhanden
  - Mindestens eine zuordnungsfaehige Bohrung (hole_single subtractive,
    nicht bereits einem Pocket zugeordnet)

Wenn eine der Vorbedingungen fehlt: Skip ohne LLM-Call.
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
    """Assigns existing hole features to pockets when the user said so.

    Runs after assembly, before blueprint_resolver. Returns a partial
    state update that re-parents matching hole features to a pocket and
    drops the original entries (the re-parented copies replace them).
    """

    name = "pocket_child_placer"
    dspy_demo_fields = {
        "input_fields": ["specification", "pockets_listing", "holes_listing"],
        "output_field": "assignments",
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
                    f"specification: {ex['spec']}\n"
                    f"pockets: {_json.dumps(ex['pockets'], ensure_ascii=False)}\n"
                    f"holes: {_json.dumps(ex['holes'], ensure_ascii=False)}",
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
          1. No spec or no blueprint                       → skip
          2. No "in der tasche"-style phrase in spec       → skip
          3. No pocket-typed feature in blueprint          → skip
          4. No assignable hole features                   → skip
          5. Otherwise: build pockets/holes listings, ask LLM
             for assignments, then re-parent each matched
             hole into a pocket-child copy.
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

        holes = self._collect_assignable_holes(blueprint)
        if not holes:
            log.debug("pocket_child_skip", reason="no_holes")
            return {}

        log.info("pocket_child_assigning",
                 pocket_count=len(pockets),
                 hole_count=len(holes),
                 spec_len=len(specification))

        try:
            assignments = self._call_llm(specification, pockets, holes)
        except Exception as e:
            log.warning("pocket_child_llm_failed", error=str(e)[:120])
            return {}

        validated = self._validate_assignments(assignments, pockets, holes)
        if not validated:
            log.info("pocket_child_no_assignments")
            return {}

        existing_ids = set((blueprint.get("features") or {}).keys())
        features_to_add: dict[str, dict] = {}
        feature_ids_to_remove: list[str] = []
        per_pocket_counter: dict[str, int] = {}

        for hole_id, pocket_id in validated:
            upstream = (blueprint.get("features") or {}).get(hole_id)
            if not isinstance(upstream, dict):
                continue
            per_pocket_counter[pocket_id] = per_pocket_counter.get(pocket_id, 0) + 1
            new_fid = self._make_child_id(
                pocket_id,
                per_pocket_counter[pocket_id],
                existing_ids | set(features_to_add.keys()),
            )
            features_to_add[new_fid] = self._reparent_hole(
                hole_id, new_fid, pocket_id, upstream,
            )
            feature_ids_to_remove.append(hole_id)

        log.info("pocket_child_done",
                 added=len(features_to_add),
                 removed=len(feature_ids_to_remove))
        return {
            "features_to_add": features_to_add,
            "feature_ids_to_remove": feature_ids_to_remove,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_pockets(blueprint: dict) -> list[dict]:
        """Walk blueprint.features and collect pocket-typed entries.

        Returns dicts with id, parent_part, x/y/depth, and a position_hint
        derived from the pocket's own placement (alignment/side).
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

    @staticmethod
    def _collect_assignable_holes(blueprint: dict) -> list[dict]:
        """Collect hole_single features that are not already pocket children.

        Excludes holes whose parent is itself a pocket (already assigned).
        Returns dicts with feature_id, durchmesser, tiefe and source_text
        (taken from the feature's notes, which carry the original user
        snippet from the feature_definierer).
        """
        features = blueprint.get("features") or {}
        if not isinstance(features, dict):
            return []
        pocket_ids = {
            fid for fid, feat in features.items()
            if isinstance(feat, dict)
            and (feat.get("type") or "").lower() in _POCKET_TYPES
            and (feat.get("operation") or "add").lower() == "subtract"
        }
        out: list[dict] = []
        for fid, feat in features.items():
            if not isinstance(feat, dict):
                continue
            if (feat.get("type") or "").lower() != "hole_single":
                continue
            if (feat.get("operation") or "add").lower() != "subtract":
                continue
            if feat.get("parent") in pocket_ids:
                continue
            params = feat.get("params") or {}
            out.append({
                "feature_id": fid,
                "durchmesser": params.get("diameter"),
                "tiefe": params.get("depth"),
                "source_text": (feat.get("notes") or "")[:120],
            })
        return out

    def _call_llm(
        self, specification: str, pockets: list[dict], holes: list[dict],
    ) -> list[dict]:
        """Call the LLM and parse the JSON response into a list of assignments."""
        pockets_listing = _json.dumps(pockets, ensure_ascii=False, indent=2)
        holes_listing = _json.dumps(holes, ensure_ascii=False, indent=2)
        prompt = POCKET_CHILD_PROMPT_TEMPLATE.format(
            specification=specification,
            pockets_listing=pockets_listing,
            holes_listing=holes_listing,
        )
        result = self.call_json(prompt, system=SYSTEM_PROMPT)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return result.get("assignments", []) or []
        return []

    @staticmethod
    def _validate_assignments(
        assignments: list[dict],
        pockets: list[dict],
        holes: list[dict],
    ) -> list[tuple[str, str]]:
        """Filter LLM output to (hole_id, pocket_id) tuples for known IDs.

        Drops assignments that:
          - Reference an unknown hole_feature_id
          - Reference an unknown pocket_id
          - Map the same hole_id more than once (first-wins)
        """
        valid_pocket_ids = {p["id"] for p in pockets}
        valid_hole_ids = {h["feature_id"] for h in holes}
        seen_holes: set[str] = set()
        out: list[tuple[str, str]] = []
        for entry in assignments or []:
            if not isinstance(entry, dict):
                continue
            hole_id = entry.get("hole_feature_id") or entry.get("hole_id")
            pocket_id = entry.get("pocket_id") or entry.get("parent_pocket_id")
            if not hole_id or not pocket_id:
                continue
            if hole_id not in valid_hole_ids:
                log.warning("pocket_child_unknown_hole",
                            hole=hole_id, valid=list(valid_hole_ids))
                continue
            if pocket_id not in valid_pocket_ids:
                log.warning("pocket_child_unknown_pocket",
                            pocket=pocket_id, valid=list(valid_pocket_ids))
                continue
            if hole_id in seen_holes:
                continue
            seen_holes.add(hole_id)
            out.append((hole_id, pocket_id))
        return out

    @staticmethod
    def _make_child_id(pocket_id: str, idx: int, taken: set[str]) -> str:
        """Build a unique child-hole id of the form hole_in_<pocket>_<idx>."""
        base = f"hole_in_{pocket_id}_{idx}"
        fid = base
        i = 2
        while fid in taken:
            fid = f"{base}_{i}"
            i += 1
        return fid

    @staticmethod
    def _reparent_hole(
        old_id: str, new_id: str, pocket_id: str, upstream: dict,
    ) -> dict:
        """Clone an upstream hole feature, re-parent to a pocket, set depth ref.

        The position dict (with center_offset / edge_distances / alignment)
        is preserved 1:1 from the upstream feature — that is the whole point
        of this refactor. The resolver's _resolve_feature_in_feature pathway
        interprets it in the pocket-local frame.
        """
        position = dict(upstream.get("position") or {})
        position["depth_reference"] = "pocket_floor"
        position.setdefault("side", "oben")
        position.setdefault("alignment", "centered")

        params = dict(upstream.get("params") or {})

        return {
            "id": new_id,
            "type": (upstream.get("type") or "hole_single").lower(),
            "parent": pocket_id,
            "operation": "subtract",
            "orientation": upstream.get("orientation") or "standard",
            "params": params,
            "position": position,
            "notes": upstream.get("notes") or "",
        }


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
