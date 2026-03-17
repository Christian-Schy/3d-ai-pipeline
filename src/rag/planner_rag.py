"""
src/rag/planner_rag.py — CSG-Tree examples for the Planner agent."""

from src.rag.base_rag import BaseRAG


class PlannerRAG(BaseRAG):
    """RAG instance for the Planner agent.

    Retrieves CSG-Tree examples relevant to the current specification.
    """
    collection_name = "planner_knowledge"
    knowledge_dir = "data/knowledge/planner"
    agent_name = "planner"
