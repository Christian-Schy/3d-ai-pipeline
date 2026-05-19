"""Assembler — resolved Feature Tree blueprint → executable CadQuery code.

Public API:
    generate_code(blueprint) -> str   — complete .py file as a string

Package layout:
    core.py            — Public API + phase orchestration + _make_func_name
    feature_codegen.py — Phase 1+2: per-feature code generation
    assembly.py        — Phase 3+4: sub-assembly builds + assemble()
    transforms.py      — .rotate()/.translate() source emitters
"""

from .core import generate_code

__all__ = ["generate_code"]
