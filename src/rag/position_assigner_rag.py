"""
src/rag/position_assigner_rag.py — Face calculation and placement knowledge for the Position Assigner.

Compact docs covering:
  - Face dimension math (which face has which dimensions)
  - Two-step placement (feature on part, then assembly)
  - Alignment keywords and offset formulas
  - Face-dependent axis mapping
"""

from src.rag.base_rag import BaseRAG


class PositionAssignerRAG(BaseRAG):
    """RAG instance for the Position Assigner agent.

    Uses 25_position_assigner/ — examples of face calculation,
    two-step placement, alignment, and offset formulas.
    """
    collection_name = "position_assigner_knowledge"
    knowledge_dir = "data/knowledge/rag_agents/25_position_assigner"
    agent_name = "position_assigner"
