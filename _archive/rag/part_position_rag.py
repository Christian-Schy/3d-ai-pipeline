"""
src/rag/part_position_rag.py — Part positioning knowledge for the Part Position Assigner.

Covers:
  - Part-to-part placement (on top, beside, floating)
  - Distance and gap calculations
  - Orientation hints for assembled parts
"""

from src.rag.base_rag import BaseRAG


class PartPositionRAG(BaseRAG):
    """RAG instance for the Part Position Assigner agent.

    Uses 28_part_position/ — examples of part positioning,
    floating parts, and gap calculations.
    """
    collection_name = "part_position_knowledge"
    knowledge_dir = "data/knowledge/rag_agents/28_part_position"
    agent_name = "part_position_assigner"
