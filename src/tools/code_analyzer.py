"""
src/code_analyzer.py — Static analysis for generated CadQuery code

Runs before the sandbox to catch obvious errors instantly.
No Ollama call needed — pure Python AST analysis.

Why this matters:
  A sandbox run takes 10-30 seconds.
  A static check takes <1 second.
  Catching obvious errors here saves a full error-loop phase.
"""

import ast
import re
import structlog
from dataclasses import dataclass, field

log = structlog.get_logger()


@dataclass
class AnalysisResult:
    """Result of static code analysis.
    
    valid=True means the code passed all checks and is ready for sandbox.
    valid=False means issues were found — see `issues` for details.
    fixed_code contains the auto-fixed version if fixes were applied.
    """
    valid: bool
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    fixed_code: str = ""        # auto-fixed version, empty if no fixes applied
    was_auto_fixed: bool = False


class CodeAnalyzer:
    """Analyzes generated CadQuery code before sandbox execution.
    
    Two modes:
      check(): returns issues without modifying code
      fix():   attempts to auto-fix common issues, returns fixed code
    """

    # Imports that must NOT appear — we inject them ourselves
    FORBIDDEN_IMPORTS = {
        "cadquery",
        "OUTPUT_PATH",
    }

    # The final shape must be stored in this variable
    REQUIRED_RESULT_VAR = "result"

    # The export call that must appear
    EXPORT_PATTERN = re.compile(r"cq\.exporters\.export\s*\(")

    def analyze(self, code: str) -> AnalysisResult:
        """Run all checks and attempt auto-fixes.
        
        Returns AnalysisResult with either clean code or a list of issues.
        Auto-fixes are applied for simple problems — complex issues
        are returned as-is so the error loop can handle them.
        """
        issues = []
        warnings = []
        working_code = code

        # --- Check 1: Syntax ---
        syntax_ok, syntax_error = self._check_syntax(working_code)
        if not syntax_ok:
            # Syntax errors can't be auto-fixed here — return immediately
            issues.append(f"Syntax error: {syntax_error}")
            log.warning("code_analyzer_syntax_error", error=syntax_error)
            return AnalysisResult(valid=False, issues=issues, fixed_code=code)

        # --- Check 2: Forbidden imports + hardcoded OUTPUT_PATH ---
        # _remove_forbidden_imports handles both import statements AND
        # OUTPUT_PATH = "..." assignments — run always, check if code changed
        cleaned = self._remove_forbidden_imports(working_code)
        if cleaned != working_code:
            forbidden = self._check_forbidden_imports(working_code)
            working_code = cleaned
            warnings.append(f"Removed redundant imports/assignments: {forbidden or ['OUTPUT_PATH']}")
            log.info("code_analyzer_removed_forbidden", warnings=warnings[-1])

        # --- Check 3: result variable ---
        has_result = self._check_result_variable(working_code)
        if not has_result:
            issues.append(
                "Missing 'result' variable. "
                "The final shape must be stored as: result = ..."
            )
            log.warning("code_analyzer_missing_result")

        # --- Check 4: export call ---
        has_export = self._check_export_call(working_code)
        if not has_export:
            if has_result:
                # Auto-fix: append the export line
                working_code = self._add_export_line(working_code)
                warnings.append("Added missing export line")
                log.info("code_analyzer_added_export")
            else:
                issues.append(
                    "Missing export call: cq.exporters.export(result, OUTPUT_PATH)"
                )

        # --- Check 5: Auto-inject .clean() after .cut() and .union() ---
        # CadQuery/OCCT produces non-manifold geometry when cut tools are coplanar
        # with the target solid. .clean() fixes this deterministically.
        cleaned_code = self._inject_clean_calls(working_code)
        if cleaned_code != working_code:
            working_code = cleaned_code
            warnings.append("Auto-injected .clean() after .cut()/.union() calls")
            log.info("code_analyzer_clean_injected")

        # --- Check 5b: Replace export with multi-tolerance retry ---
        # Some boolean operations (e.g. slot + through-hole overlap) produce
        # non-watertight STL at the default tolerance=0.1. Trying finer tessellation
        # often resolves the topology artifact without code changes.
        retry_code = self._inject_export_tolerance_retry(working_code)
        if retry_code != working_code:
            working_code = retry_code
            warnings.append("Auto-wrapped export with tolerance retry")
            log.info("code_analyzer_export_retry_injected")

        # --- Check 6: Common bad patterns ---
        pattern_issues = self._check_bad_patterns(working_code)
        issues.extend(pattern_issues)

        # --- Summary ---
        was_fixed = (working_code != code)
        is_valid = len(issues) == 0

        if issues:
            log.warning("code_analyzer_issues_found", count=len(issues), issues=issues)
        elif warnings:
            log.info("code_analyzer_warnings", count=len(warnings), warnings=warnings)
        else:
            log.info("code_analyzer_clean")

        return AnalysisResult(
            valid=is_valid,
            issues=issues,
            warnings=warnings,
            fixed_code=working_code if was_fixed or is_valid else code,
            was_auto_fixed=was_fixed,
        )

    # --- Individual checks ---

    def _check_syntax(self, code: str) -> tuple[bool, str]:
        """Parse the code with Python's AST. Returns (ok, error_message)."""
        try:
            ast.parse(code)
            return True, ""
        except SyntaxError as e:
            return False, f"line {e.lineno}: {e.msg}"

    def _check_forbidden_imports(self, code: str) -> list[str]:
        """Find imports that we inject ourselves — model must not add them."""
        found = []
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in self.FORBIDDEN_IMPORTS:
                            found.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module and any(
                        f in node.module for f in self.FORBIDDEN_IMPORTS
                    ):
                        found.append(node.module)
        except SyntaxError:
            pass
        return found

    def _check_result_variable(self, code: str) -> bool:
        """Check that 'result' is assigned somewhere in the code."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "result":
                            return True
                elif isinstance(node, ast.AugAssign):
                    if isinstance(node.target, ast.Name) and node.target.id == "result":
                        return True
        except SyntaxError:
            pass
        return False

    def _check_export_call(self, code: str) -> bool:
        """Check that cq.exporters.export() is called."""
        return bool(self.EXPORT_PATTERN.search(code))

    def _check_bad_patterns(self, code: str) -> list[str]:
        """Check for known problematic patterns from common_errors.md."""
        issues = []

        # Pattern: exportStl() — old API, removed in recent CadQuery
        if "exportStl" in code:
            issues.append(
                "Found deprecated exportStl() call. "
                "Use: cq.exporters.export(result, OUTPUT_PATH)"
            )

        # Pattern: result.export() — wrong method
        if re.search(r"result\.export\s*\(", code):
            issues.append(
                "Found result.export() which is not valid. "
                "Use: cq.exporters.export(result, OUTPUT_PATH)"
            )

        # Pattern: cutBlind with positive value (usually wrong direction)
        if re.search(r"\.cutBlind\s*\(\s*[1-9]", code):
            issues.append(
                "cutBlind() called with positive value — this cuts outward. "
                "Use negative value to cut into the solid: .cutBlind(-depth)"
            )

        # Pattern: fillet/chamfer before any solid creation
        lines = code.split("\n")
        first_fillet = next(
            (i for i, l in enumerate(lines) if ".fillet(" in l or ".chamfer(" in l),
            None
        )
        first_solid = next(
            (i for i, l in enumerate(lines)
             if ".box(" in l or ".cylinder(" in l or ".sphere(" in l
             or ".extrude(" in l or ".circle(" in l or ".rect(" in l),
            None
        )
        if first_fillet is not None and first_solid is not None:
            if first_fillet < first_solid:
                issues.append(
                    "fillet/chamfer appears before any solid is created. "
                    "Always apply fillets and chamfers last."
                )

        return issues

    # --- Auto-fixes ---

    def _inject_clean_calls(self, code: str) -> str:
        """Add .clean() after every .cut(...) and .union(...) that doesn't already have it.

        CadQuery's .clean() runs OpenCASCADE geometry healing which fixes coplanar
        face artifacts that cause non-manifold (non-watertight) STL output.
        This is deterministic — no model cooperation needed.
        """
        # Match .cut(...) or .union(...) possibly followed by more chained calls,
        # but NOT already followed by .clean()
        # We process line by line to handle multi-line chains
        lines = code.split("\n")
        result_lines = []
        for line in lines:
            # Add .clean() after .cut(…) or .union(…) unless already present
            # Pattern: any occurrence of .cut(...) or .union(...) at end of expression
            # We check if .clean() is already in the line to avoid double injection
            stripped = line.rstrip()
            if ".clean()" not in stripped:
                # Replace .cut(…) with .cut(…).clean() — handles nested parens via greedy
                new_line = re.sub(
                    r'(\.cut\([^)]*\))((?!\.clean\(\)))',
                    r'\1.clean()\2',
                    stripped,
                )
                new_line = re.sub(
                    r'(\.union\([^)]*\))((?!\.clean\(\)))',
                    r'\1.clean()\2',
                    new_line,
                )
                result_lines.append(new_line)
            else:
                result_lines.append(line)
        return "\n".join(result_lines)

    def _inject_export_tolerance_retry(self, code: str) -> str:
        """Replace cq.exporters.export(result, OUTPUT_PATH) with a tolerance retry loop.

        Some OCCT booleans produce non-watertight STL at default tolerance=0.1mm.
        Retrying with finer tessellation (0.01) resolves most artifacts.
        Already-parameterized export calls (with tolerance=...) are left unchanged.
        """
        # Only inject if there's a plain export call without tolerance kwarg
        plain_export = re.compile(
            r"cq\.exporters\.export\s*\(\s*result\s*,\s*OUTPUT_PATH\s*\)"
        )
        if not plain_export.search(code):
            return code  # already has custom params or no export — skip

        retry_block = (
            "# Auto-injected: try multiple tolerances for watertight export\n"
            "for _export_tol in [0.1, 0.01, 0.5]:\n"
            "    cq.exporters.export(result, OUTPUT_PATH,\n"
            "                        tolerance=_export_tol, angularTolerance=0.2)\n"
            "    try:\n"
            "        import trimesh as _tm\n"
            "        _m = _tm.load(OUTPUT_PATH, force='mesh')\n"
            "        if _m.is_watertight or getattr(_m, 'euler_number', 0) == 2:\n"
            "            break\n"
            "    except Exception:\n"
            "        break  # trimesh unavailable — use first export"
        )

        return plain_export.sub(retry_block, code)

    def _remove_forbidden_imports(self, code: str) -> str:
        """Remove import lines for things we inject (cadquery, OUTPUT_PATH)."""
        clean_lines = []
        for line in code.split("\n"):
            stripped = line.strip()
            # Skip: import cadquery, import cadquery as cq, from cadquery import ...
            if re.match(r"^import cadquery", stripped):
                continue
            if re.match(r"^from cadquery import", stripped):
                continue
            # Skip: OUTPUT_PATH = "..."  (hardcoded path)
            if re.match(r"^OUTPUT_PATH\s*=", stripped.lstrip()):
                continue
            clean_lines.append(line)
        return "\n".join(clean_lines)

    def _add_export_line(self, code: str) -> str:
        """Append the export call at the end of the code."""
        # Remove any trailing blank lines first
        code = code.rstrip()
        return code + "\ncq.exporters.export(result, OUTPUT_PATH)\n"