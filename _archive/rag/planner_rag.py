"""
src/rag/planner_rag.py — Geometry rules and placement patterns for the Planner."""

from src.rag.base_rag import BaseRAG


class PlannerRAG(BaseRAG):
    """RAG instance for the Planner agent.

    Uses agent-specific geometry docs (21_planner_geometry) —
    compact docs with coordinate formulas, face-selector rules, and
    build-order patterns. No CadQuery code — geometry only.
    """
    collection_name = "planner_geometry"
    knowledge_dir = "data/knowledge/rag_agents/21_planner_geometry"
    agent_name = "planner"
