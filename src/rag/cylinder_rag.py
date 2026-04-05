"""
src/rag/cylinder_rag.py — Cylinder-specific CadQuery knowledge for the Coder.

Injected when agent_flags contains 'inject_cylinder_rag'.
Covers: full cylinders, hollow cylinders, cylinder positioning, cylinder subtraction.
"""

from src.rag.base_rag import BaseRAG


class CylinderRAG(BaseRAG):
    """RAG instance for cylinder-specific CadQuery patterns.

    Uses 26_cylinder_patterns/ — CadQuery examples for creating,
    positioning, and modifying cylinders.
    """
    collection_name = "cylinder_patterns_knowledge"
    knowledge_dir = "data/knowledge/rag_agents/26_cylinder_patterns"
    agent_name = "coder_cylinder"
