"""
src/rag/blueprint_rag.py — RAG for the Blueprint Architect agent.

Consolidated knowledge from all former planning agents (20-28) into
a single collection (30_blueprint). Contains:
  - Feature types & trigger words
  - Face rules & offset formulas
  - Parent assignment & build order
  - Orientation patterns
  - Pattern examples (grid, circular, linear)
  - Multi-part examples
  - Common mistakes
  - Geometry rules
"""

from src.rag.base_rag import BaseRAG


class BlueprintRAG(BaseRAG):
    """RAG instance for the Blueprint Architect agent.

    Single consolidated collection replacing 8 former per-agent RAGs.
    Knowledge dir: data/knowledge/rag_agents/30_blueprint/
    """
    collection_name = "blueprint_knowledge"
    knowledge_dir = "data/knowledge/rag_agents/30_blueprint"
    agent_name = "blueprint_architect"
