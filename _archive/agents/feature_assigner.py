"""
src/agents/feature_assigner.py — Assigns parent, operation, and dimensions to each feature.

Part of the "Häppchen" architecture:
  Feature Tagger → **Feature Assigner** → Position Assigner → Blueprint Assembler → Planner

The Feature Assigner's ONLY job:
  - For each feature identified by the Feature Tagger, determine:
    1. parent — which feature is this attached to?
    2. operation — add (union) or subtract (cut)?
    3. params — exact dimensions from the specification

It does NOT determine positions, offsets, or faces — that's the Position Assigner's job.

Model: qwen3.5:9b — focused task, text understanding only, no geometry calculation.
"""

import structlog
from src.agents.base import BaseAgent
from src.config.loader import get_config
from src.graph.state import PipelineState
from src.utils.prompt_loader import load_prompt
from src.rag.feature_assigner_rag import FeatureAssignerRAG

log = structlog.get_logger()

_prompt = load_prompt("prompt_feature_assigner.py")
SYSTEM_PROMPT = _prompt.SYSTEM_PROMPT
RAG_INJECTION_TEMPLATE = _prompt.RAG_INJECTION_TEMPLATE


class FeatureAssignerAgent(BaseAgent):
    """Assigns structure (parent, operation, dimensions) to each feature.

    Reads the feature list from Feature Tagger and the specification,
    then determines for each feature what it is, where it belongs,
    and what its dimensions are.
    """

    name = "feature_assigner"

    def __init__(self):
        super().__init__()
        self._rag = FeatureAssignerRAG()
        self._rag_ready = False

    def _ensure_rag(self):
        if not self._rag_ready:
            try:
                self._rag.build()
            except FileNotFoundError:
                self.log.warning("feature_assigner_rag_missing",
                                 path="data/knowledge/rag_agents/24_feature_assigner")
            self._rag_ready = True

    @property
    def model(self) -> str:
        return get_config().models.feature_assigner

    def assign(self, state: PipelineState) -> dict:
        """Assign parent, operation, and params to each feature.

        Returns dict with:
          feature_assignments: {feature_id: {parent, operation, params}}
        """
        specification = state.get("specification") or state.get("description", "")
        feature_tree = state.get("feature_tree", {})
        features = feature_tree.get("features_identified", [])

        if not features:
            self.log.warning("feature_assigner_no_features")
            return {"feature_assignments": {}, "build_order_assigned": []}

        # Build a compact feature list string for the prompt
        feature_lines = []
        for f in features:
            if isinstance(f, dict):
                fid = f.get("id", "unknown")
                ftype = f.get("type", "unknown")
                feature_lines.append(f"{fid} ({ftype})")
            elif isinstance(f, str):
                feature_lines.append(f)
        feature_list_str = ", ".join(feature_lines)

        prompt = RAG_INJECTION_TEMPLATE.format(
            specification=specification,
            feature_list=feature_list_str,
        )

        self._ensure_rag()
        prompt = self._rag.enrich_prompt(prompt, specification)

        try:
            result = self.call_json(prompt, system=SYSTEM_PROMPT)

            # Debug: log the raw response structure so we can diagnose parsing failures
            self.log.info("feature_assigner_raw_response",
                          keys=list(result.keys()) if isinstance(result, dict) else type(result).__name__,
                          sample={k: type(v).__name__ for k, v in (result.items() if isinstance(result, dict) else [])})

            # Robust key detection: LLMs sometimes use alternative key names
            assignments = result.get("assignments", {})
            if not isinstance(assignments, dict) or not assignments:
                for alt_key in ("feature_assignments", "features", "feature_list"):
                    assignments = result.get(alt_key, {})
                    if isinstance(assignments, dict) and assignments:
                        self.log.info("feature_assigner_alt_key", key=alt_key)
                        break
                else:
                    # Last resort: if result itself looks like assignments
                    # (keys are feature IDs with dict values containing "parent" or "params")
                    if isinstance(result, dict) and any(
                        isinstance(v, dict) and ("parent" in v or "params" in v)
                        for v in result.values()
                    ):
                        assignments = {k: v for k, v in result.items()
                                       if isinstance(v, dict) and ("parent" in v or "params" in v)}
                        self.log.info("feature_assigner_bare_dict",
                                      features=len(assignments))

            if not isinstance(assignments, dict):
                assignments = {}

            # Fix renamed IDs: remap back to original Feature Tagger IDs
            original_ids = {f.get("id") for f in features if isinstance(f, dict)}
            if original_ids and assignments:
                assignments = self._fix_renamed_ids(assignments, original_ids, features)

            build_order = result.get("build_order", [])
            if not isinstance(build_order, list):
                build_order = list(assignments.keys())

            # Validate: ensure every feature has required fields
            for fid, data in assignments.items():
                if not isinstance(data, dict):
                    assignments[fid] = {"parent": None, "operation": "add", "params": {}}
                    continue
                if "parent" not in data:
                    data["parent"] = None
                if "operation" not in data:
                    data["operation"] = "add"
                if "params" not in data:
                    data["params"] = {}

                # Ensure grooves/slots always have 'length' key
                params = data.get("params", {})
                if "width" in params and "depth" in params and "length" not in params:
                    params["length"] = None
                    self.log.info("feature_assigner_added_length", feature=fid)

            if not assignments:
                self.log.warning("feature_assigner_empty",
                                 result_keys=list(result.keys()) if isinstance(result, dict) else "not_dict")

            self.log.info("feature_assigner_done",
                          features=len(assignments),
                          build_order=build_order)

            return {
                "feature_assignments": assignments,
            }

        except (ValueError, ConnectionRefusedError) as e:
            self.log.error("feature_assigner_failed", error=str(e))
            return {
                "feature_assignments": {},
            }

    @staticmethod
    def _fix_renamed_ids(assignments: dict, original_ids: set, features: list) -> dict:
        """Remap renamed feature IDs back to original Feature Tagger IDs.

        LLMs sometimes rename feature IDs despite being told not to.
        This matches renamed IDs to originals by type and position.
        """
        assigned_ids = set(assignments.keys())
        if assigned_ids == original_ids:
            return assignments  # No renaming

        # Find IDs that are in assignments but not in originals (renamed)
        extra = assigned_ids - original_ids
        missing = original_ids - assigned_ids

        if not extra or not missing:
            return assignments

        # Build type map from original features
        orig_type_map = {}
        orig_order = []
        for f in features:
            if isinstance(f, dict):
                fid = f.get("id", "")
                ftype = f.get("type", "")
                orig_type_map[fid] = ftype
                orig_order.append(fid)

        # Try to match extra IDs to missing IDs by type or position
        remapped = {}
        extra_list = sorted(extra)
        missing_list = sorted(missing)

        for eid in extra_list:
            edata = assignments[eid]
            best_match = None

            # Match by similar name or type
            for mid in missing_list:
                if mid in remapped.values():
                    continue
                mtype = orig_type_map.get(mid, "")
                # Check if the extra ID contains the type name or vice versa
                if mtype and (mtype in eid or eid in mtype):
                    best_match = mid
                    break
                # Check partial name match
                eid_parts = set(eid.split("_"))
                mid_parts = set(mid.split("_"))
                if eid_parts & mid_parts:
                    best_match = mid
                    break

            if not best_match and missing_list:
                # Fallback: match by position (same index in sorted order)
                remaining = [m for m in missing_list if m not in remapped.values()]
                if remaining:
                    best_match = remaining[0]

            if best_match:
                remapped[eid] = best_match

        if remapped:
            new_assignments = {}
            for fid, data in assignments.items():
                new_fid = remapped.get(fid, fid)
                # Also fix parent references
                if isinstance(data, dict) and data.get("parent") in remapped:
                    data["parent"] = remapped[data["parent"]]
                new_assignments[new_fid] = data

            import structlog
            structlog.get_logger().info("feature_assigner_id_remap",
                                         remap=remapped)
            return new_assignments

        return assignments
