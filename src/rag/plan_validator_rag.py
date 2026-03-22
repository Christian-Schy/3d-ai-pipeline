"""
src/rag/plan_validator_rag.py — Validation rules for the Plan Validator agent.

Compact docs (max 300 tokens) with common blueprint errors and how to detect them.
"""

from src.rag.base_rag import BaseRAG


class PlanValidatorRAG(BaseRAG):
    """RAG instance for the Plan Validator agent.

    Uses 22_plan_validation/ — compact checklist docs with common blueprint
    error patterns (missing placement, wrong build_order, dimension mismatches).
    """
    collection_name = "plan_validation_rules"
    knowledge_dir = "data/knowledge/rag_agents/22_plan_validation"
    agent_name = "plan_validator"
