"""
src/agents/feature_tagger.py — Identifies all features and classifies the task.

Part of the "Häppchen" architecture:
  Interpreter → **Feature Tagger** → Feature Assigner → Position Assigner → ...

Simplified role (v2):
  - Identify features (IDs + types)
  - Assign RAG tags per feature
  - Classify the task (template selection, difficulty)

Does NOT assign parents, dimensions, positions, or build order.
Those are handled by Feature Assigner and Position Assigner.

Model: qwen3.5:9b — identification only, no geometry calculation needed.
"""

import structlog
from src.agents.base import BaseAgent
from src.config.loader import get_config
from src.graph.state import PipelineState
from src.utils.prompt_loader import load_prompt
from src.rag.feature_tagger_rag import FeatureTaggerRAG

log = structlog.get_logger()

_prompt = load_prompt("prompt_feature_tagger.py")
SYSTEM_PROMPT = _prompt.SYSTEM_PROMPT


class FeatureTaggerAgent(BaseAgent):
    """Identifies all geometric features and classifies the task.

    Outputs a feature list (IDs + types + RAG tags) and task classification.
    Parent assignment and dimensions are handled by downstream agents.
    """

    name = "feature_tagger"

    @property
    def model(self) -> str:
        return get_config().models.feature_tagger

    def __init__(self):
        super().__init__()
        self._rag = FeatureTaggerRAG()
        self._rag_ready = False

    def _ensure_rag(self):
        if not self._rag_ready:
            try:
                self._rag.build()
            except FileNotFoundError:
                self.log.warning("feature_tagger_rag_missing",
                                 path="data/knowledge/rag_agents/20_feature_catalog")
            self._rag_ready = True

    @staticmethod
    def _consolidate_patterns(features: list) -> list:
        """Merge duplicate hole entries into a single hole_pattern_grid.

        The 9b model sometimes splits "4 Eckbohrungen" into 4 separate
        hole_single entries. This merges them into one hole_pattern_grid.
        """
        if not features or not isinstance(features, list):
            return features

        # Find groups of hole_single with similar IDs (hole_corner_1..4, etc.)
        import re
        hole_groups: dict[str, list[int]] = {}  # base_name → [indices]
        for i, f in enumerate(features):
            if not isinstance(f, dict):
                continue
            ftype = f.get("type", "")
            fid = f.get("id", "")
            if ftype == "hole_single" and re.match(r"(.+?)_?\d+$", fid):
                base = re.match(r"(.+?)_?\d+$", fid).group(1)
                hole_groups.setdefault(base, []).append(i)

        # Merge groups with 3+ entries into one hole_pattern_grid
        indices_to_remove = set()
        inserts = []
        for base, indices in hole_groups.items():
            if len(indices) < 3:
                continue
            # Merge: keep the first entry, change type, remove the rest
            first = features[indices[0]]
            merged = {
                "id": base.rstrip("_"),
                "type": "hole_pattern_grid",
                "rag_tags": first.get("rag_tags", ["corner_holes", "pattern"]),
            }
            inserts.append((indices[0], merged))
            indices_to_remove.update(indices)

        if not indices_to_remove:
            return features

        # Rebuild feature list
        result = []
        for i, f in enumerate(features):
            if i in indices_to_remove:
                # Check if this index has a replacement
                for ins_idx, ins_feat in inserts:
                    if ins_idx == i:
                        result.append(ins_feat)
                        break
            else:
                result.append(f)

        return result

    def tag(self, state: PipelineState) -> dict:
        """Identify features and classify the task.

        Returns dict with feature_tree and task_classification.
        """
        specification = state.get("specification") or state.get("description", "")
        change_desc = state.get("change_description", "")
        text_to_analyze = change_desc if change_desc else specification

        prompt = f"Specification to analyze:\n{text_to_analyze}"

        self._ensure_rag()
        prompt = self._rag.enrich_prompt(prompt, text_to_analyze)

        try:
            result = self.call_json(prompt, system=SYSTEM_PROMPT)

            features = result.get("features", [])

            # Consolidate: if the LLM split a pattern into individual entries,
            # merge them back into one hole_pattern_grid.
            features = self._consolidate_patterns(features)

            # Collect rag_tags from each feature
            rag_queries = []
            for feat in features:
                if isinstance(feat, dict):
                    rag_queries.extend(feat.get("rag_tags", []))
            rag_queries = list(dict.fromkeys(rag_queries))

            tc = result.get("task_classification", {})

            self.log.info("feature_tagger_done",
                          features_count=len(features),
                          task_type=tc.get("task_type", "?"),
                          template=tc.get("planner_template", "?"))

            return {
                "feature_tree": {
                    "features_identified": features,
                    "dependencies": [],  # No longer assigned here
                    "rag_queries": rag_queries,
                },
                "feature_specs": [],  # No longer assigned here
                "task_classification": {
                    "task_type": tc.get("task_type", "complex_multi_step"),
                    "difficulty": tc.get("difficulty", "medium"),
                    "requires_current_geometry": bool(tc.get("requires_current_geometry", False)),
                    "rag_categories": tc.get("rag_categories", []),
                    "planner_template": tc.get("planner_template", "template_complex"),
                    "warnings": tc.get("warnings", []),
                },
            }

        except (ValueError, ConnectionRefusedError) as e:
            self.log.warning("feature_tagger_fallback", error=str(e))
            return {
                "feature_tree": {
                    "features_identified": [],
                    "dependencies": [],
                    "rag_queries": [],
                },
                "feature_specs": [],
                "task_classification": {
                    "task_type": "complex_multi_step",
                    "difficulty": "high",
                    "requires_current_geometry": False,
                    "rag_categories": ["holes_single", "boolean_ops"],
                    "planner_template": "template_complex",
                    "warnings": [],
                },
            }
