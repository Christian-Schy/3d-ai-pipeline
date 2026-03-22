"""
src/tools/cq_linter.py — Deterministic CadQuery code linter.

Runs in code_review_node BEFORE the LLM reviewer.
Uses Python's compile() + AST walk — no LLM cost, instant, 100% reliable.

If ERROR-severity issues are found, code_review_node returns them immediately
without invoking the LLM. The Coder gets specific fix instructions and retries.

Checks:
  1. Syntax (compile())
  2. Missing cq.exporters.export() call
  3. OUTPUT_PATH not used in export
  4. Missing import cadquery
  5. Modular code without assemble() function
  6. assemble() defined but never called
  7. AST: uncaptured .union()/.cut()/.intersect() results
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field


@dataclass
class LintIssue:
    severity: str   # "ERROR" or "WARNING"
    check: str      # short check identifier
    message: str    # human-readable description
    line: int = 0   # source line (0 = unknown)

    def as_text(self) -> str:
        loc = f" (line {self.line})" if self.line else ""
        return f"[{self.severity}] {self.check}{loc}: {self.message}"


def lint_cadquery_code(code: str) -> list[LintIssue]:
    """Run all lint checks on generated CadQuery code.

    Returns list of LintIssue objects. Empty list = all checks passed.
    Stops immediately and returns on SyntaxError (further AST checks would crash).
    """
    if not code or not code.strip():
        return [LintIssue("ERROR", "empty_code", "Code is empty")]

    issues: list[LintIssue] = []

    # ── Check 1: Syntax ──────────────────────────────────────────────
    try:
        compile(code, "<generated>", "exec")
    except SyntaxError as e:
        return [LintIssue(
            "ERROR", "syntax",
            f"SyntaxError: {e.msg}",
            line=e.lineno or 0,
        )]

    # ── Check 2: import cadquery ─────────────────────────────────────
    # NOTE: sandbox.py always prepends 'import cadquery as cq' before execution,
    # so missing import is only a WARNING here (code will still run).
    if "import cadquery" not in code:
        issues.append(LintIssue(
            "WARNING", "missing_import",
            "No 'import cadquery as cq' found — sandbox injects it, but better to include explicitly",
        ))

    # ── Check 3: exporters.export() call ─────────────────────────────
    if "exporters.export" not in code:
        issues.append(LintIssue(
            "ERROR", "missing_export",
            "No cq.exporters.export() call found — STL will not be written",
        ))
    elif "OUTPUT_PATH" not in code:
        issues.append(LintIssue(
            "WARNING", "hardcoded_path",
            "exporters.export() uses a hardcoded path instead of OUTPUT_PATH variable",
        ))

    # ── Check 4: modular structure integrity ─────────────────────────
    is_modular = any(
        f"def {prefix}_" in code
        for prefix in ("make", "add", "drill", "cut", "apply", "hollow", "engrave", "emboss", "subtract")
    )
    has_assemble_def = "def assemble(" in code
    has_assemble_call = "result = assemble()" in code

    if is_modular and not has_assemble_def:
        issues.append(LintIssue(
            "ERROR", "missing_assemble",
            "Modular functions (make_/add_/drill_/cut_) detected but no assemble() function defined",
        ))

    if has_assemble_def and not has_assemble_call:
        issues.append(LintIssue(
            "ERROR", "missing_assemble_call",
            "assemble() is defined but never called — add: result = assemble()",
        ))

    # ── Check 5: AST — uncaptured boolean operations ─────────────────
    _check_uncaptured_booleans(code, issues)

    return issues


def _check_uncaptured_booleans(code: str, issues: list[LintIssue]) -> None:
    """Walk AST to find .union()/.cut()/.intersect() results that are discarded.

    Pattern: standalone expression statement that is a method call on
    one of the boolean-operation methods. This means the result is
    thrown away — the body stays unchanged — a silent bug.

    Example (bad):   result.union(tool)
    Example (good):  result = result.union(tool).clean()
    """
    BOOLEAN_METHODS = {"union", "cut", "intersect", "shell"}
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return  # already caught in check 1

    for node in ast.walk(tree):
        if not isinstance(node, ast.Expr):
            continue
        call = node.value
        if not isinstance(call, ast.Call):
            continue
        func = call.func
        # Direct method call: foo.union(...)
        if isinstance(func, ast.Attribute) and func.attr in BOOLEAN_METHODS:
            issues.append(LintIssue(
                "ERROR", "uncaptured_boolean",
                f".{func.attr}() result not captured — use: result = result.{func.attr}(...).clean()",
                line=node.lineno,
            ))


def format_lint_issues(issues: list[LintIssue]) -> str:
    """Format issues as a short text block for the Coder's fix prompt."""
    lines = ["Linter found the following issues (fix ALL before proceeding):"]
    for issue in issues:
        lines.append(f"  {issue.as_text()}")
    return "\n".join(lines)


def has_errors(issues: list[LintIssue]) -> bool:
    return any(i.severity == "ERROR" for i in issues)
