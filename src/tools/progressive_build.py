"""
src/tools/progressive_build.py — Function-by-function execution for modular code.

Activated when:
  - Code uses the modular assemble() pattern (has make_base / add_* / drill_* functions)
  - Blueprint has 3+ features (single-feature models use classic single-build)

Strategy:
  For each function in build_order order:
    1. Build a test script: imports + constants + all functions + partial assemble
    2. Run in sandbox with a short timeout
    3. If it fails → report which function is broken

This gives the Coder a precise error like:
  "drill_bohrung(body) failed: ValueError: distance cannot be 0"
instead of:
  "Line 47: ValueError: distance cannot be 0"

Only runs on FAILURE of the full build — is not a pre-flight check.
"""

from __future__ import annotations

import ast
import re
import textwrap
import structlog

log = structlog.get_logger()


def _extract_function_names(code: str) -> list[str]:
    """Extract all top-level function names from the code using AST."""
    try:
        tree = ast.parse(code)
        return [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        ]
    except SyntaxError:
        # Fall back to regex if code has syntax errors
        return re.findall(r"^def (\w+)\(", code, re.MULTILINE)


def _extract_function_body(code: str, func_name: str) -> str:
    """Extract the complete definition of a named function."""
    lines = code.splitlines()
    start = None
    body_lines = []

    for i, line in enumerate(lines):
        if re.match(rf"^def {re.escape(func_name)}\s*\(", line):
            start = i
        if start is not None:
            body_lines.append(line)
            # Stop at the next top-level def or end of file
            if i > start and line and not line[0].isspace() and not line.startswith("#"):
                body_lines.pop()  # remove the start of next function
                break

    return "\n".join(body_lines)


def _extract_preamble(code: str) -> str:
    """Extract imports and top-level constants (non-function, non-class lines)."""
    lines = code.splitlines()
    preamble = []
    in_func = False

    for line in lines:
        if re.match(r"^def \w+", line) or re.match(r"^class \w+", line):
            in_func = True
        elif line and not line[0].isspace() and not line.startswith("#"):
            in_func = False

        if not in_func:
            # Skip export/run lines at the end
            stripped = line.strip()
            if stripped.startswith("result =") or stripped.startswith("cq.exporters"):
                continue
            preamble.append(line)

    return "\n".join(preamble)


def _build_partial_test_script(
    preamble: str,
    all_functions: dict[str, str],
    build_sequence: list[str],
    up_to_func: str,
    output_path: str,
) -> str:
    """Build a test script that runs the build chain up to and including up_to_func.

    Args:
        preamble:       Import + constant lines
        all_functions:  {func_name: full_source} for all defined functions
        build_sequence: Ordered list of call expressions (e.g. ["make_base()", "add_steg(result)"])
        up_to_func:     Stop after this function call
        output_path:    Where to export the partial STL
    """
    lines = [preamble, ""]

    # Include all function definitions (needed for type hints / forward refs)
    for src in all_functions.values():
        lines.append(src)
        lines.append("")

    # Build up to and including up_to_func
    lines.append("# === PROGRESSIVE BUILD TEST ===")
    for call_expr in build_sequence:
        func_name_match = re.match(r"(\w+)\(", call_expr)
        func_name = func_name_match.group(1) if func_name_match else ""

        # build_* functions return a standalone part — don't assign to result yet
        if func_name.startswith("build_"):
            part_var = func_name.replace("build_", "")
            lines.append(f"{part_var} = {call_expr}")
            # Progressive build can't test translate+union, just build the part
            lines.append(f"result = {part_var}  # partial: standalone sub-assembly")
        elif "make_" in call_expr:
            lines.append(f"result = {call_expr}")
        else:
            lines.append(f"result = {call_expr}")

        if func_name == up_to_func:
            break

    lines.append(f'cq.exporters.export(result, "{output_path}")')
    return "\n".join(lines)


def _infer_build_sequence(code: str, build_order: list[str]) -> list[str]:
    """Infer the call sequence from the assemble() function body."""
    # Try to extract from assemble()
    match = re.search(r"def assemble\(\)[^:]*:(.*?)(?=\ndef |\Z)", code, re.DOTALL)
    if match:
        body = match.group(1)
        # Only use lines that are indented (= inside the function body)
        # This filters out "result = assemble()" at module level
        indented_body = "\n".join(
            line for line in body.splitlines()
            if not line.strip() or line.startswith(" ") or line.startswith("\t")
        )
        # Find all "var = func(...)" lines — captures both "result = " and "part_name = "
        calls = re.findall(r"\w+\s*=\s*(\w+\([^)]*\))", indented_body)
        # Filter out: self-reference, method chains, translate, union, clean
        calls = [
            c for c in calls
            if not c.startswith("assemble(")
            and not c.startswith("result.")
            and not c.startswith("cq.")
            and ".translate" not in c
            and ".union" not in c
            and ".clean" not in c
        ]
        if calls:
            return calls

    # Fallback: reconstruct from build_order
    sequence = []
    for i, fid in enumerate(build_order):
        if i == 0:
            sequence.append(f"make_{fid}()")
        else:
            # Guess function prefix from common patterns
            for prefix in ("make_", "add_", "drill_", "cut_", "apply_"):
                candidate = f"{prefix}{fid}"
                if candidate in code:
                    sequence.append(f"{candidate}(result)")
                    break
            else:
                sequence.append(f"add_{fid}(result)")

    return sequence


def run_progressive_build(
    code: str,
    blueprint: dict,
    sandbox,
    base_output_path: str,
) -> dict:
    """Run the code function-by-function to find the first failing function.

    Only call this AFTER a full-build failure to diagnose the root cause.

    Args:
        code:             The generated CadQuery code.
        blueprint:        Feature Tree blueprint dict.
        sandbox:          Sandbox instance to run code in.
        base_output_path: Base path for partial STL outputs (will suffix with _step_n).

    Returns:
        {
            "failing_function": str or None,
            "error": str,
            "step": int,  # which step failed (0-indexed)
            "partial_results": [{"function": str, "success": bool}]
        }
    """
    from src.graph.feature_tree import FeatureTree

    if not FeatureTree.is_feature_tree(blueprint):
        return {"failing_function": None, "error": "", "step": -1, "partial_results": []}

    build_order: list[str] = blueprint.get("build_order", [])
    if len(build_order) < 3:
        # Only useful for 3+ features (roadmap requirement)
        return {"failing_function": None, "error": "", "step": -1, "partial_results": []}

    func_names = _extract_function_names(code)
    preamble = _extract_preamble(code)
    build_sequence = _infer_build_sequence(code, build_order)

    # Collect all function source bodies
    all_functions: dict[str, str] = {}
    for fname in func_names:
        if fname == "assemble":
            continue
        body = _extract_function_body(code, fname)
        if body:
            all_functions[fname] = body

    log.info("progressive_build_start",
             build_steps=len(build_sequence),
             functions=list(all_functions.keys()))

    partial_results = []
    for i, call_expr in enumerate(build_sequence):
        func_name_match = re.match(r"(\w+)\(", call_expr)
        func_name = func_name_match.group(1) if func_name_match else f"step_{i}"

        step_output = base_output_path.replace(".stl", f"_step{i}.stl")
        test_script = _build_partial_test_script(
            preamble, all_functions, build_sequence, func_name, step_output
        )

        result = sandbox.run(code=test_script, output_path=step_output)
        step_result = {"function": func_name, "success": result.success}
        partial_results.append(step_result)

        log.info("progressive_build_step",
                 step=i, function=func_name, success=result.success)

        if not result.success:
            log.warning("progressive_build_failed_at",
                        function=func_name, step=i, error=result.error[:200])
            return {
                "failing_function": func_name,
                "error": result.error,
                "step": i,
                "partial_results": partial_results,
            }

    # All steps passed (shouldn't happen since we only call this after full failure)
    log.info("progressive_build_all_passed")
    return {
        "failing_function": None,
        "error": "",
        "step": -1,
        "partial_results": partial_results,
    }


def format_progressive_error(result: dict) -> str:
    """Format progressive build result as a focused error message for the Coder."""
    func = result.get("failing_function")
    if not func:
        return ""

    error = result.get("error", "")
    step = result.get("step", -1)
    passed = [r["function"] for r in result.get("partial_results", []) if r["success"]]

    lines = [
        f"Progressive build: failure in step {step + 1} — function `{func}()`",
        f"Error: {error[:300]}",
    ]
    if passed:
        lines.append(f"Passed before failure: {', '.join(passed)}")
    lines.append(f"\nFix ONLY the function `{func}()`. All previous functions work correctly.")
    return "\n".join(lines)
