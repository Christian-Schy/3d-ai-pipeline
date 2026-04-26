"""
src/sandbox.py — Safe CadQuery code execution with pre-run analysis

Flow:
  1. CodeAnalyzer checks the code statically (< 1 second)
  2. If auto-fixable issues found: fix them silently
  3. If blocking issues found: return failure immediately (no subprocess wasted)
  4. If clean: run in subprocess with timeout
"""

import sys
import subprocess
import structlog
from dataclasses import dataclass
from src.tools.code_analyzer import CodeAnalyzer, AnalysisResult
from src.tools.stl_validator import STLValidator

log = structlog.get_logger()


@dataclass
class ExecutionResult:
    """The result of running generated code in the sandbox.
    
    success=True means the code ran without errors.
    was_analyzed=True means static analysis ran before execution.
    was_auto_fixed=True means the analyzer patched the code before running.
    """
    success: bool
    error: str = ""
    was_analyzed: bool = False
    was_auto_fixed: bool = False


class Sandbox:
    """Runs generated CadQuery code safely in a subprocess.
    
    Why subprocess and not exec()?
    exec() would run untrusted code inside our own process — a crash there
    would crash the whole pipeline. subprocess isolates it: if the code
    crashes, only that child process dies.

    Static analysis runs first to catch obvious errors without wasting
    a full subprocess execution (which takes 10-30 seconds for CadQuery).
    """

    def __init__(self, timeout: int = 60):
        self.timeout = timeout
        self._analyzer = CodeAnalyzer()
        self._validator = STLValidator()

    def run(self, code: str, output_path: str) -> ExecutionResult:
        """Analyze then run the code. Returns success or failure with details."""

        # --- Step 1: Static analysis ---
        analysis = self._analyzer.analyze(code)

        if analysis.was_auto_fixed:
            log.info("sandbox_code_auto_fixed", warnings=analysis.warnings)
            code = analysis.fixed_code  # use the fixed version

        if not analysis.valid:
            # Blocking issues found — no need to run the subprocess
            error_summary = " | ".join(analysis.issues)
            log.warning("sandbox_blocked_by_analysis", issues=analysis.issues)
            return ExecutionResult(
                success=False,
                error=f"Static analysis failed:\n" + "\n".join(
                    f"  - {issue}" for issue in analysis.issues
                ),
                was_analyzed=True,
                was_auto_fixed=analysis.was_auto_fixed,
            )

        # --- Step 2: Run in subprocess ---
        # Inject cadquery import and output path before the model's code
        header = f'import cadquery as cq\nOUTPUT_PATH = r"{output_path}"\n\n'
        full_code = header + code

        try:
            result = subprocess.run(
                [sys.executable, "-c", full_code],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            log.error("sandbox_timeout", timeout=self.timeout)
            return ExecutionResult(
                success=False,
                error=f"Timeout: code took longer than {self.timeout}s",
                was_analyzed=True,
                was_auto_fixed=analysis.was_auto_fixed,
            )

        if result.returncode == 0:
            # --- Step 3: STL validation ---
            # Code ran without errors, but the geometry might still be broken
            validation = self._validator.validate(output_path)
            if not validation.valid:
                issue_summary = " | ".join(validation.issues)
                log.warning("sandbox_stl_invalid", issues=validation.issues)
                return ExecutionResult(
                    success=False,
                    error=f"STL geometry invalid:\n" + "\n".join(
                        f"  - {issue}" for issue in validation.issues
                    ),
                    was_analyzed=True,
                    was_auto_fixed=analysis.was_auto_fixed,
                )
            log.info("sandbox_success", output_path=output_path,
                     triangles=validation.stats.get("triangles"),
                     volume_mm3=validation.stats.get("volume_mm3"))
            return ExecutionResult(
                success=True,
                was_analyzed=True,
                was_auto_fixed=analysis.was_auto_fixed,
            )
        else:
            error_output = result.stderr or result.stdout or "Unknown error (no output captured)"
            log.error("sandbox_error", stderr=result.stderr[:200], stdout=result.stdout[:100])
            return ExecutionResult(
                success=False,
                error=error_output,
                was_analyzed=True,
                was_auto_fixed=analysis.was_auto_fixed,
            )