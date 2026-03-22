"""
src/rag/code_review_rag.py — Code review rules for the Code Review agent.

Compact docs (max 300 tokens) with common CadQuery code anti-patterns.
"""

from src.rag.base_rag import BaseRAG


class CodeReviewRAG(BaseRAG):
    """RAG instance for the Code Review agent.

    Uses 23_code_review/ — compact docs with CadQuery anti-patterns,
    common coding mistakes, and review checklist items.
    """
    collection_name = "code_review_rules"
    knowledge_dir = "data/knowledge/rag_agents/23_code_review"
    agent_name = "code_review"
