"""
src/config/loader.py — Loads and validates config.yaml with Pydantic.

Usage anywhere in the codebase:
    from src.config.loader import get_config
    cfg = get_config()
    model = cfg.models.coder        # e.g. "nemotron-cascade-2:30b"
    timeout = cfg.sandbox.timeout_seconds

The config is loaded once and cached — subsequent calls are free.
If config.yaml is missing or has wrong types, a clear error is raised
at startup instead of a cryptic crash later.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

# Relative to this file: src/config/loader.py → ../../config/config.yaml
CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "config.yaml"


# ------------------------------------------------------------------
# Pydantic models — one per config section
# ------------------------------------------------------------------

class OllamaConfig(BaseModel):
    base_url: str = "http://localhost:11434"
    timeout_seconds: int = 300
    think: bool = False          # qwen3/qwen3.5: disable chain-of-thought for speed
    temperature: float = 0.15   # lower = more deterministic JSON output
    num_ctx: int = 8192          # context window in tokens


class AgentOptions(BaseModel):
    """Per-agent overrides — only set fields that differ from global ollama defaults."""
    model_config = {"extra": "ignore"}
    think: bool | None = None
    temperature: float | None = None
    num_ctx: int | None = None


class ModelsConfig(BaseModel):
    model_config = {"extra": "ignore"}
    # Entry / Modification
    interpreter: str = "qwen3.5:9b"
    modification_interpreter: str = "qwen3.5:9b"
    visioner: str = "qwen3.5:27b"
    punctuation: str = "qwen3.5:9b"

    # Blueprint Chain (3-Step + Multi-Part split)
    inventar: str = "qwen3.5:9b"
    aktions_klassifizierer: str = "qwen3.5:9b"
    hole_classifier: str = "qwen3.5:9b"
    pocket_classifier: str = "qwen3.5:9b"
    slot_classifier: str = "qwen3.5:9b"
    grid_classifier: str = "qwen3.5:9b"
    circular_classifier: str = "qwen3.5:9b"
    linear_classifier: str = "qwen3.5:9b"
    edge_feature_classifier: str = "qwen3.5:9b"
    position_extractor: str = "qwen3.5:9b"
    text_splitter: str = "qwen3.5:9b"
    normalizer: str = "qwen3.5:9b"
    platzierer: str = "qwen3.5:9b"
    assembly: str = "qwen3.5:9b"

    # Validation + Codegen
    plan_validator: str = "qwen3.5:9b"
    coder: str = "qwen3-coder:30b"
    validator: str = "qwen3.5:9b"
    code_fixer: str = "qwen3.5:9b"


class RagKnowledgeConfig(BaseModel):
    model_config = {"extra": "ignore"}
    coder: str = "data/knowledge/rag"
    validator: str = "data/knowledge/rag_agents/22_plan_validation"
    interpreter: str = "data/knowledge/rag/16_interpreter_knowledge"
    visioner: str = "data/knowledge/rag"


class RagNResultsConfig(BaseModel):
    """Per-agent chunk count. Lower for small focused knowledge bases."""
    model_config = {"extra": "ignore"}
    coder: int = 4
    validator: int = 3
    interpreter: int = 2
    visioner: int = 2
    plan_validator: int = 2
    code_review: int = 2


class RagConfig(BaseModel):
    embedding_model: str = "all-MiniLM-L6-v2"
    db_path: str = "data/rag_db"
    n_results: RagNResultsConfig = Field(default_factory=RagNResultsConfig)
    knowledge: RagKnowledgeConfig = Field(default_factory=RagKnowledgeConfig)


class SandboxConfig(BaseModel):
    timeout_seconds: int = 60
    output_dir: str = "data/output"


class ErrorLoopConfig(BaseModel):
    max_attempts: int = 6
    max_semantic_retries: int = 2
    disable_coder: bool = True
    """Coder-Elimination (Memory project_coder_elimination, feedback_template_mode_no_coder).

    Default true — alle Routes die historisch auf 'coder' gegangen sind
    (route_after_validator placement-error, route_after_error_router phase=1,
    route_after_function_decomposer mode=llm, route_after_code_review issues)
    enden stattdessen am END. Der Run wird mit dem aktuellen Pipeline-State
    gespeichert (kein STL bei Codegen-Fail, aber Blueprint+Traces fuer Analyse).
    Auf False setzen reaktiviert den alten LLM-Coder-Pfad."""


class UIConfig(BaseModel):
    server_host: str = "0.0.0.0"
    server_port: int = 7860
    share: bool = False
    log_lines_visible: int = 50


class PlanValidatorConfig(BaseModel):
    max_retries: int = 2


class ClassifierSubagentsConfig(BaseModel):
    """Feature flags for ADR-0006/0009 classifier sub-agents.

    Default false keeps runtime identical to the monolithic classifier until
    each sub-agent is trained and adopted via heatmap. The ADR-0009 pattern
    split (grid/circular/linear) replaces the former `pattern_enabled` flag.
    """
    hole_enabled: bool = False
    pocket_enabled: bool = False
    slot_enabled: bool = False
    grid_enabled: bool = False
    circular_enabled: bool = False
    linear_enabled: bool = False
    edge_feature_enabled: bool = False


class AppConfig(BaseModel):
    """Root config object. All sections have sensible defaults
    so the app works even if config.yaml is partially missing."""
    model_config = {"extra": "ignore"}
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    rag: RagConfig = Field(default_factory=RagConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    error_loop: ErrorLoopConfig = Field(default_factory=ErrorLoopConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    agent_options: dict[str, AgentOptions] = Field(default_factory=dict)
    plan_validator: PlanValidatorConfig = Field(default_factory=PlanValidatorConfig)
    classifier_subagents: ClassifierSubagentsConfig = Field(
        default_factory=ClassifierSubagentsConfig
    )

    def get_agent_options(self, agent_name: str) -> tuple[bool, float, int]:
        """Return (think, temperature, num_ctx) for an agent, merging global + per-agent."""
        g = self.ollama
        o = self.agent_options.get(agent_name, AgentOptions())
        return (
            o.think       if o.think       is not None else g.think,
            o.temperature if o.temperature is not None else g.temperature,
            o.num_ctx     if o.num_ctx     is not None else g.num_ctx,
        )


# ------------------------------------------------------------------
# Loader
# ------------------------------------------------------------------

def _load_config(path: Path) -> AppConfig:
    """Load and validate a config file. Separated for testability."""
    if not path.exists():
        return AppConfig()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return AppConfig.model_validate(raw)


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Load config.yaml and return a validated AppConfig.

    Cached after first call — free to call anywhere.
    Falls back to all-defaults if config.yaml doesn't exist.
    """
    return _load_config(CONFIG_PATH)
