"""
src/rag/coder_rag.py — CadQuery knowledge base for the Coder agent.

Phase 3: Multi-tag RAG queries driven by Feature Tagger output.

The Coder gets two types of RAG context:
  1. Per-tag queries: one ChromaDB query per rag_query from Feature Tagger
     → targeted, no noise from unrelated features
  2. Always-include files: two fixed docs injected directly from disk
     → modular_function_style.md + modular_assembly_pattern.md
"""

import hashlib
from pathlib import Path

import structlog

from src.rag.base_rag import BaseRAG

log = structlog.get_logger()

# Fixed docs always included for Feature Tree pipeline (modular code style)
ALWAYS_INCLUDE_FILES = [
    "data/knowledge/rag/14_code_patterns/modular_function_style.md",
    "data/knowledge/rag/13_composition/modular_assembly_pattern.md",
]


class CoderRAG(BaseRAG):
    """RAG instance for the Coder agent.

    Phase 3: uses multi-tag queries from Feature Tagger instead of
    a single description query. Falls back to single-query mode for
    legacy (non-Feature-Tree) blueprints.
    """

    collection_name = "coder_knowledge"
    knowledge_dir = "data/knowledge/rag"   # numbered collections 01-15 (CadQuery examples)
    agent_name = "coder"

    def query_multi_tag(self, rag_queries: list[str], n_per_query: int = 2) -> list[dict]:
        """Fire one ChromaDB query per tag and deduplicate results.

        Each query fetches up to n_per_query chunks. Results from all
        queries are merged and deduplicated by source+text identity.

        Returns list of dicts: {'text': ..., 'source': ..., 'distance': ...}
        """
        seen_ids: set[str] = set()
        all_chunks: list[dict] = []

        for query_text in rag_queries:
            chunks = self.query(query_text, n_results=n_per_query)
            for chunk in chunks:
                key = f"{chunk['source']}:{chunk['text'][:80]}"
                if key not in seen_ids:
                    seen_ids.add(key)
                    all_chunks.append(chunk)

        self.log.info("rag_multi_tag_done",
                      queries=len(rag_queries),
                      unique_chunks=len(all_chunks))
        return all_chunks

    def enrich_prompt_with_tags(
        self,
        prompt: str,
        rag_queries: list[str],
        include_always: bool = True,
    ) -> str:
        """Inject multi-tag RAG context + always-include files into the prompt.

        Args:
            prompt:         The prompt string to enrich.
            rag_queries:    Query strings from Feature Tagger (one per feature/tag).
            include_always: Whether to inject the fixed always-include docs.

        Updates self.last_chunks_used with source names used.
        """
        context_parts = ["\n## Relevant Reference\n"]
        context_parts.append(
            "The following examples are relevant to this task. "
            "Use them as reference — adapt to the specific blueprint.\n"
        )

        ref_index = 1
        chunks_used: list[str] = []

        # 1. Always-include files (read directly from disk, no vector search)
        if include_always:
            for file_path_str in ALWAYS_INCLUDE_FILES:
                file_path = Path(file_path_str)
                if file_path.exists():
                    content = file_path.read_text(encoding="utf-8")
                    context_parts.append(f"\n### Reference {ref_index} (from {file_path.name}):\n")
                    context_parts.append(f"```\n{content[:1200]}\n```\n")
                    chunks_used.append(file_path.name)
                    ref_index += 1
                else:
                    self.log.warning("rag_always_include_missing", path=file_path_str)

        # 2. Per-tag queries from Feature Tagger
        if rag_queries:
            tag_chunks = self.query_multi_tag(rag_queries, n_per_query=2)
            for chunk in tag_chunks:
                context_parts.append(f"\n### Reference {ref_index} (from {chunk['source']}):\n")
                context_parts.append(f"```\n{chunk['text']}\n```\n")
                chunks_used.append(chunk["source"])
                ref_index += 1

        self.last_chunks_used = list(dict.fromkeys(chunks_used))

        if ref_index == 1:
            # Nothing was added — return prompt unchanged
            return prompt

        context = "\n".join(context_parts)

        # Insert before blueprint section if present, else prepend
        lower = prompt.lower()
        if "blueprint:" in lower or "feature tree blueprint" in lower:
            insert_at = prompt.find("\n\n")
            if insert_at > 0:
                return prompt[:insert_at] + "\n\n" + context + "\n" + prompt[insert_at:]
        return context + "\n\n" + prompt

    def save_successful_code(self, blueprint: dict, code: str) -> bool:
        """Save a successful blueprint→code pair as a new RAG example.

        Called by validator_node on success. Over time this builds up a
        library of working examples specific to this installation's models.

        The document is formatted so future queries can find it by description
        or feature type (e.g. 'hole', 'chamfer', 'slot').

        Returns True if a new entry was added, False if already present.
        """
        from src.graph.feature_tree import FeatureTree

        description = blueprint.get("description", "")
        if not description or not code:
            return False

        # Extract feature types for searchability
        if FeatureTree.is_feature_tree(blueprint):
            build_order = blueprint.get("build_order", [])
            features_raw = blueprint.get("features", {})
            feature_types = [
                features_raw.get(fid, {}).get("type", "")
                for fid in build_order
                if features_raw.get(fid, {}).get("type")
            ]
        else:
            features_raw = blueprint.get("features", [])
            if isinstance(features_raw, list):
                feature_types = [f.get("type", "") for f in features_raw if isinstance(f, dict)]
            else:
                feature_types = []

        feature_str = ", ".join(feature_types) if feature_types else "base_shape"

        doc = (
            f"# Auto-learned Example: {description}\n"
            f"# Features: {feature_str}\n\n"
            f"```python\n{code}\n```\n"
        )

        # Stable ID: same description + same feature set → same ID (no duplicates)
        doc_id_raw = f"auto_{description}_{feature_str}"
        doc_id = hashlib.md5(doc_id_raw.encode()).hexdigest()

        return self.add_example(
            doc_text=doc,
            doc_id=doc_id,
            metadata={
                "source": "auto_learned.py",
                "type": "auto_learned",
                "description": description[:100],
                "features": feature_str[:100],
            },
        )
