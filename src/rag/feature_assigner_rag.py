"""
src/rag/feature_assigner_rag.py — Per-part thinking and parent assignment knowledge for the Feature Assigner.

Compact docs covering:
  - Per-part isolated thinking (each part independent)
  - Parent assignment rules (feature → nearest part)
  - Operation mapping (add vs subtract)
  - Params extraction from text
"""

from src.rag.base_rag import BaseRAG


class FeatureAssignerRAG(BaseRAG):
    """RAG instance for the Feature Assigner agent.

    Uses 24_feature_assigner/ — examples of per-part thinking,
    parent assignment, and dimension extraction.
    """
    collection_name = "feature_assigner_knowledge"
    knowledge_dir = "data/knowledge/rag_agents/24_feature_assigner"
    agent_name = "feature_assigner"
