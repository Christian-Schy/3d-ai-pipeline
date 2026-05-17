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


def load_convention(name: str) -> str:
    """Load a shared prompt-convention fragment from data/prompts/conventions/.

    A fragment is a plain-text block injected verbatim into classifier
    SYSTEM_PROMPTs (ADR 0014 W2 — Konventions-Bibliothek). One fragment
    encodes one DIN/positioning convention; editing the file propagates
    the change to every prompt that includes it, so a convention can
    never again live in only one of several sibling classifiers.

    `name` is the file stem without extension, e.g. "ecken_regel".
    """
    path = Path("data/prompts/conventions") / f"{name}.md"
    return path.read_text(encoding="utf-8").strip()
