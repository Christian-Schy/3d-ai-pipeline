"""
src/rag/coder_rag.py — CadQuery knowledge base for the Coder agent.

Inherits everything from BaseRAG.
Only sets collection_name and knowledge_dir — no other logic needed.

The knowledge files in data/knowledge/coder/ come from v1 and contain:
  - Working CadQuery code examples
  - Common error patterns and their fixes
  - API reference snippets
"""

from src.rag.base_rag import BaseRAG


class CoderRAG(BaseRAG):
    """RAG instance for the Coder agent.

    Retrieves CadQuery examples and error hints relevant to
    the current blueprint before the Coder writes its code.
    """

    collection_name = "coder_knowledge"
    knowledge_dir = "data/knowledge/coder"
    agent_name = "coder"
