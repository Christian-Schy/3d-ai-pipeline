"""
src/rag/feature_tagger_rag.py — Feature catalog for the Feature Tagger agent.

Compact docs (max 300 tokens) covering all feature types.
Used to supplement the system prompt when unusual feature combinations appear.
"""

from src.rag.base_rag import BaseRAG


class FeatureTaggerRAG(BaseRAG):
    """RAG instance for the Feature Tagger agent.

    Uses 20_feature_catalog/ — small collection of feature type examples.
    n_results=1 because the full catalog fits in the system prompt;
    RAG only adds 1 clarifying example for edge cases.
    """
    collection_name = "feature_tagger_catalog"
    knowledge_dir = "data/knowledge/rag_agents/20_feature_catalog"
    agent_name = "feature_tagger"
