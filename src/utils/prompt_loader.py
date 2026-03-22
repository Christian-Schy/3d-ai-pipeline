"""
src/utils/prompt_loader.py — Loads Python-based prompt modules from data/prompts/.

Usage in agents:
    from src.utils.prompt_loader import load_prompt
    _p = load_prompt("prompt_coder.py")
    SYSTEM_PROMPT = _p.SYSTEM_PROMPT
"""

import importlib.util
from pathlib import Path
from types import ModuleType


def load_prompt(filename: str) -> ModuleType:
    """Load a Python prompt file from data/prompts/ and return the module.

    The module is loaded relative to the current working directory (project root).
    All module-level variables (SYSTEM_PROMPT, RAG_INJECTION_TEMPLATE, ...) are
    accessible as attributes on the returned module.
    """
    path = Path("data/prompts") / filename
    module_name = filename.removesuffix(".py")
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
