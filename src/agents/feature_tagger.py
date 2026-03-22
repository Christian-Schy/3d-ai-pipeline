"""
src/agents/feature_tagger.py — Identifies all features and their relationships.

Identifies all features and their relationships.

Outputs two things:
  feature_tree:       Preliminary feature list (IDs, types, rag_tags, dependencies)
                      Used by PromptAssembler for targeted RAG queries.
                      Stored in state.feature_tree.

  task_classification: Dict for PromptAssembler template selection.
                      task_type, difficulty, rag_categories, planner_template,
                      warnings, requires_current_geometry.

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
    """Identifies all geometric features and their parent-child relationships.

    The Feature Tagger identifies ALL features, assigns RAG tags per feature,
    and builds a dependency tree that guides the Planner.

    Also emits task_classification for backward-compat with PromptAssembler.
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

    def tag(self, state: PipelineState) -> dict:
        """Identify features and classify the task.

        Returns dict with feature_tree and task_classification.
        """
        specification = state.get("specification") or state.get("description", "")
        change_desc = state.get("change_description", "")
        text_to_analyze = change_desc if change_desc else specification

        context = ""
        previous_bp = state.get("previous_blueprint", {})
        if previous_bp and change_desc:
            context = (
                f"\nExisting model: {previous_bp.get('description', '')}\n"
                f"Features: {len(previous_bp.get('features', []) or previous_bp.get('features', {}))}\n"
            )

        # Use interpreter pre-analysis as a starting hint (avoids duplicate work)
        interpreter_features = state.get("interpreter_features", [])
        hint_section = ""
        if interpreter_features:
            hint_lines = "\n".join(f"  - {f}" for f in interpreter_features)
            hint_section = (
                f"\nInterpreter pre-analysis (already resolved positions — use as starting point):\n"
                f"{hint_lines}\n"
            )

        prompt = f"Specification to analyze:\n{text_to_analyze}{context}{hint_section}"

        self._ensure_rag()
        prompt = self._rag.enrich_prompt(prompt, text_to_analyze)

        try:
            result = self.call_json(prompt, system=SYSTEM_PROMPT)

            features = result.get("features", [])
            dependencies = result.get("dependencies", [])
            build_order = result.get("build_order", [])

            # Collect rag_tags from each feature into a flat query list.
            rag_queries = result.get("rag_queries", [])
            if not rag_queries:
                for feat in features:
                    if isinstance(feat, dict):
                        rag_queries.extend(feat.get("rag_tags", []))
                rag_queries = list(dict.fromkeys(rag_queries))  # deduplicate, preserve order

            tc = result.get("task_classification", {})

            task_type = tc.get("task_type", "complex_multi_step")
            difficulty = tc.get("difficulty", "medium")
            requires_geo = bool(tc.get("requires_current_geometry", False))
            rag_cats = tc.get("rag_categories", [])
            template = tc.get("planner_template", "template_complex")
            warnings = tc.get("warnings", [])

            # --- Build feature_specs for per-feature planning ---
            # Each spec contains: id, type, parent, rag_tags, description_relative
            feature_specs = []
            # Build parent lookup from dependencies
            parent_map: dict[str, str | None] = {}
            for dep in dependencies:
                if isinstance(dep, dict):
                    parent_map[dep.get("child", "")] = dep.get("parent")

            # If build_order is missing, derive from features list order
            if not build_order:
                build_order = [f.get("id", f"f{i}") for i, f in enumerate(features)
                               if isinstance(f, dict)]

            for fid in build_order:
                # Find the matching feature dict
                feat_dict = next(
                    (f for f in features if isinstance(f, dict) and f.get("id") == fid),
                    None
                )
                if not feat_dict:
                    continue
                feature_specs.append({
                    "id": fid,
                    "type": feat_dict.get("type", "unknown"),
                    "parent": parent_map.get(fid),
                    "rag_tags": feat_dict.get("rag_tags", []),
                    "description_relative": feat_dict.get("description_relative", ""),
                })

            self.log.info("feature_tagger_done",
                          features_count=len(features),
                          feature_specs_count=len(feature_specs),
                          build_order=build_order,
                          task_type=task_type,
                          template=template,
                          warnings=warnings)

            return {
                "feature_tree": {
                    "features_identified": features,
                    "dependencies": dependencies,
                    "rag_queries": rag_queries,
                },
                "feature_specs": feature_specs,
                "task_classification": {
                    "task_type": task_type,
                    "difficulty": difficulty,
                    "requires_current_geometry": requires_geo,
                    "rag_categories": rag_cats,
                    "planner_template": template,
                    "warnings": warnings,
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
