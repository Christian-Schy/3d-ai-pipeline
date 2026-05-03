"""Function Decomposer — turns a Feature Tree into a Python code skeleton.

Sits between Plan-Validator and Coder. Rule-based, no LLM call.

Public API:
    FunctionDecomposerAgent — pipeline-facing agent (mode classification + dispatch)
    generate_skeleton       — pure function: Feature Tree blueprint → skeleton string

Internal modules:
    naming     — function names + slot-axis detection
    positions  — geometric helpers (offsets, face centers, NTP eligibility)
    docstrings — per-feature docstring builder
    constants  — dimension + offset constant emission
    grouping   — sub-assembly grouping
    skeleton_linear        — flat one-function-per-feature emission
    skeleton_sub_assembly  — build-parts-standalone-then-union emission
    skeleton   — entry point that picks one of the two emitters
    agent      — FunctionDecomposerAgent class
"""

from .agent import FunctionDecomposerAgent
from .skeleton import generate_skeleton

__all__ = ["FunctionDecomposerAgent", "generate_skeleton"]
