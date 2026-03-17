"""
src/rag/interpreter_rag.py — Knowledge base for the Interpreter agent.

Contains examples of:
  - Vague user requests + the clarifying questions that resolved them
  - Complete, well-formed specifications the Planner can work with
  - Common ambiguities in 3D model descriptions

This helps the Interpreter ask the right questions and recognize
when a specification is complete enough to pass to the Planner.
"""

from src.rag.base_rag import BaseRAG


class InterpreterRAG(BaseRAG):
    """RAG instance for the Interpreter agent.

    Retrieves examples of good specifications and useful clarifying
    questions relevant to the current user request.
    """

    collection_name = "interpreter_knowledge"
    knowledge_dir = "data/knowledge/interpreter"
    agent_name = "interpreter"
