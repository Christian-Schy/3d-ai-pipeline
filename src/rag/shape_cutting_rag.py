"""
src/rag/shape_cutting_rag.py — Shape-cutting CadQuery knowledge for the Coder.

Injected when agent_flags contains 'inject_shape_rag'.
Covers: polyline cuts, arc cuts, triangle cuts, custom shapes, sagittaArc, radiusArc.
"""

from src.rag.base_rag import BaseRAG


class ShapeCuttingRAG(BaseRAG):
    """RAG instance for shape-cutting CadQuery patterns.

    Uses 27_shape_cutting/ — CadQuery examples for cutting and adding
    arbitrary 2D shapes (triangles, arcs, polygons, custom profiles).
    """
    collection_name = "shape_cutting_knowledge"
    knowledge_dir = "data/knowledge/rag_agents/27_shape_cutting"
    agent_name = "coder_shape"
