# AGENT CONFIG — Schnellreferenz für den Coder-Claude
# Welcher Agent bekommt welches Modell, welchen Prompt, welches RAG

"""
AGENT-KONFIGURATIONEN
=====================

Jeder Agent ist ein LangGraph-Node mit:
- model: welches LLM (oder regelbasiert)
- prompt: System-Prompt Template
- rag_dir: welches RAG-Verzeichnis
- rag_n_results: wieviele RAG-Chunks
- json_mode: ob JSON-Output erzwungen wird
- temperature: Sampling-Temperatur
- max_tokens: Output-Limit
"""

AGENT_CONFIGS = {

    "interpreter": {
        "model": "qwen3.5:9b",
        "prompt_file": "prompts/prompt_interpreter.py",
        "rag_dir": "rag/16_interpreter_knowledge/",
        "rag_n_results": 2,
        "rag_max_tokens": 600,
        "json_mode": True,
        "temperature": 0.3,
        "max_tokens": 500,
        "notes": "Sprache → Geometrie. Kein CadQuery-Wissen. Löst implizite Positionen auf."
    },

    "feature_tagger": {
        "model": "qwen3.5:9b",
        "prompt_file": "prompts/prompt_feature_tagger.py",
        "rag_dir": "rag_agents/20_feature_catalog/",
        "rag_n_results": 1,  # Katalog ist klein genug für System-Prompt
        "rag_max_tokens": 400,
        "json_mode": True,
        "temperature": 0.1,
        "max_tokens": 400,
        "notes": "Enum-basiert. Kompakt halten! 9b wird bei >1500 Token RAG unzuverlässig."
    },

    "planner": {
        "model": "qwen3.5:35b",
        "prompt_file": "prompts/prompt_planner.py",
        "rag_dir": "rag_agents/21_planner_geometry/",
        "rag_n_results": 3,
        "rag_max_tokens": 2500,
        "json_mode": True,
        "temperature": 0.3,
        "max_tokens": 2000,
        "notes": "Geometrisches Reasoning. Chain-of-Thought. KEIN CadQuery-Code im RAG."
    },

    "coordinate_validator": {
        "model": None,  # REGELBASIERT — kein LLM
        "prompt_file": None,
        "rag_dir": None,
        "notes": "Python-Funktion: Prüft Dimensionen, Positionen, Plausibilität."
    },

    "plan_validator": {
        "model": "qwen3.5:9b",
        "prompt_file": "prompts/prompt_plan_validator.py",
        "rag_dir": "rag_agents/22_plan_validation/",
        "rag_n_results": 2,
        "rag_max_tokens": 400,
        "json_mode": True,
        "temperature": 0.1,
        "max_tokens": 500,
        "notes": "Checklisten-basiert. Kompakt. Bekommt Blueprint + Spezifikation."
    },

    "function_decomposer": {
        "model": None,  # REGELBASIERT — kein LLM
        "prompt_file": "prompts/function_decomposer.py",  # Python-Funktion, kein Prompt
        "rag_dir": None,
        "notes": "Template-Engine. Generiert Skeleton aus Feature Tree. Deterministisch."
    },

    "coder": {
        "model": "qwen3-coder:30b",
        "prompt_file": "prompts/prompt_coder.py",
        "rag_dir": "rag/",  # Unterverzeichnisse 01-15
        "rag_n_results": 4,
        "rag_max_tokens": 4000,
        "rag_query_source": "feature_tagger.rag_tags",  # Tags vom Feature Tagger steuern RAG
        "rag_always_include": [
            "rag/14_code_patterns/modular_function_style.md",
            "rag/13_composition/modular_assembly_pattern.md"
        ],
        "json_mode": False,  # Code-Output, kein JSON
        "temperature": 0.2,
        "max_tokens": 4000,
        "notes": "CadQuery-Experte. Bekommt Skeleton + Blueprint + RAG-Beispiele."
    },

    "code_review": {
        "model": "qwen3.5:9b",
        "prompt_file": "prompts/prompt_code_review.py",
        "rag_dir": "rag_agents/23_code_review/",
        "rag_n_results": 2,
        "rag_max_tokens": 400,
        "json_mode": True,
        "temperature": 0.1,
        "max_tokens": 500,
        "notes": "Checklisten-basiert. Vergleicht Code mit Blueprint. Kompakt."
    },

    "geometry_checker": {
        "model": None,  # REGELBASIERT — kein LLM
        "prompt_file": None,
        "rag_dir": None,
        "notes": "Python-Funktion: BBox, Volumen, Feature-Existenz prüfen."
    },
}


# RAG-QUERY-STRATEGIE
# ==================
#
# 1. Interpreter: Query = User-Beschreibung → 16_interpreter_knowledge/
# 2. Feature Tagger: Kein dynamisches RAG (Katalog im System-Prompt)
# 3. Planner: Query = Feature-Typen aus Tagger → 21_planner_geometry/
# 4. Plan Validator: Query = Feature-Typen → 22_plan_validation/
# 5. Coder: Query = rag_tags vom Feature Tagger → 01-15_*/
#    PLUS immer: modular_function_style.md + modular_assembly_pattern.md
# 6. Code Review: Query = "review checklist" → 23_code_review/
#
# Feature Tagger steuert das Coder-RAG:
# Beispiel: Feature Tagger erkennt ["hole_pattern_circular", "extrusion_rect"]
# → RAG-Queries: "bolt_circle", "extrusion" → Docs aus 05_holes + 04_extrusion
# → Plus Kompositions-Docs wenn Dependencies vorhanden


# FEHLER-ROUTING
# =============
#
# Plan Validator FAIL → zurück zu Planner (mit Fehlerbeschreibung)
#   Max 2 Retries, dann weiter zum Coder mit Warnung
#
# Code Review FAIL (ERROR) → zurück zu Coder
#   Nur die fehlerhafte Funktion wird neu generiert (FIX_PROMPT_TEMPLATE)
#   Max 2 Retries, dann weiter zum Executor
#
# Geometry Checker FAIL → zurück zu Coder
#   Spezifisches Feature + Fehlerbeschreibung
#   Max 2 Retries, dann Pipeline FAIL
#
# Code Review WARNING → weiter zum Executor (kein Retry)
