"""
src/config/loader.py — Loads and validates config.yaml with Pydantic.

Usage anywhere in the codebase:
    from src.config.loader import get_config
    cfg = get_config()
    model = cfg.models.planner      # "qwen3:30b"
    timeout = cfg.sandbox.timeout_seconds

The config is loaded once and cached — subsequent calls are free.
If config.yaml is missing or has wrong types, a clear error is raised
at startup instead of a cryptic crash later.
"""

from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from pydantic import BaseModel, Field
import yaml

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
    interpreter: str = "qwen3.5:9b"
    planner: str = "qwen3.5:27b"
    planner_patch: str = "qwen3.5:9b"
    planner_revise: str = "qwen3.5:9b"
    coder: str = "qwen3-coder:30b"
    validator: str = "qwen3.5:9b"
    code_fixer: str = "qwen3.5:9b"
    visioner: str = "qwen3.5:27b"
    modification_interpreter: str = "qwen3.5:9b"
    task_classifier: str = "qwen3.5:9b"
    plan_validator: str = "qwen3.5:9b"


class RagKnowledgeConfig(BaseModel):
    coder: str = "data/knowledge/coder"
    planner: str = "data/knowledge/planner"
    validator: str = "data/knowledge/validator"
    interpreter: str = "data/knowledge/interpreter"
    visioner: str = "data/knowledge/visioner"


class RagNResultsConfig(BaseModel):
    """Per-agent chunk count. Planner needs fewer examples than Coder."""
    model_config = {"extra": "ignore"}
    coder: int = 4
    planner: int = 2
    validator: int = 3
    interpreter: int = 3
    visioner: int = 2


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


class UIConfig(BaseModel):
    server_host: str = "0.0.0.0"
    server_port: int = 7860
    share: bool = False
    log_lines_visible: int = 50


class BambuConfig(BaseModel):
    model_config = {"extra": "ignore"}
    serial: str = ""
    access_code: str = ""
    region: str = "eu"
    orca_path: str = "~/OrcaSlicer_Linux_AppImage_Ubuntu2404_V2.3.1.AppImage"
    printer_profile: str = "Bambu Lab P1S 0.4 nozzle"
    filament_profile: str = "Bambu PLA Basic @BBL P1S"
    ams_slot: int = 1


class PlanValidatorConfig(BaseModel):
    max_retries: int = 2


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
