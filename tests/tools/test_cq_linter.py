"""
tests/tools/test_cq_linter.py — Unit tests for the deterministic CadQuery linter.

Pure Python — no LLM, no RAG, no sandbox.
"""

import pytest
from src.tools.cq_linter import lint_cadquery_code, format_lint_issues, has_errors, LintIssue


# ── Helpers ──────────────────────────────────────────────────────────────────

def _errors(issues):
    return [i for i in issues if i.severity == "ERROR"]


def _warnings(issues):
    return [i for i in issues if i.severity == "WARNING"]


def _checks(issues):
    return {i.check for i in issues}


# ── Minimal valid code ────────────────────────────────────────────────────────

VALID_SIMPLE = """\
import cadquery as cq
OUTPUT_PATH = "output.stl"

result = cq.Workplane("XY").box(10, 10, 10)
cq.exporters.export(result, OUTPUT_PATH)
"""

VALID_MODULAR = """\
import cadquery as cq
import math
OUTPUT_PATH = "output.stl"

def make_base() -> cq.Workplane:
    return cq.Workplane("XY").box(50, 50, 20)

def drill_hole(body: cq.Workplane) -> cq.Workplane:
    return body.faces(">Z").workplane().hole(10).clean()

def assemble() -> cq.Workplane:
    result = make_base()
    result = drill_hole(result)
    return result

result = assemble()
cq.exporters.export(result, OUTPUT_PATH)
"""


class TestEmptyCode:
    def test_empty_string(self):
        issues = lint_cadquery_code("")
        assert has_errors(issues)
        assert "empty_code" in _checks(issues)

    def test_whitespace_only(self):
        issues = lint_cadquery_code("   \n  \t  ")
        assert has_errors(issues)
        assert "empty_code" in _checks(issues)


class TestSyntaxCheck:
    def test_syntax_error_detected(self):
        bad = "def foo(:\n    pass"
        issues = lint_cadquery_code(bad)
        assert has_errors(issues)
        assert "syntax" in _checks(issues)

    def test_syntax_stops_further_checks(self):
        bad = "def foo(:\n    pass"
        issues = lint_cadquery_code(bad)
        # Only the syntax issue should be present — no further checks
        assert len(issues) == 1

    def test_valid_syntax_no_syntax_error(self):
        issues = lint_cadquery_code(VALID_SIMPLE)
        assert "syntax" not in _checks(issues)


class TestMissingImport:
    def test_missing_import_is_warning(self):
        code = """\
OUTPUT_PATH = "output.stl"
result = cq.Workplane("XY").box(10, 10, 10)
cq.exporters.export(result, OUTPUT_PATH)
"""
        issues = lint_cadquery_code(code)
        # Must be WARNING, NOT ERROR (sandbox injects the import)
        import_issues = [i for i in issues if i.check == "missing_import"]
        assert import_issues, "Expected a missing_import warning"
        assert all(i.severity == "WARNING" for i in import_issues)

    def test_present_import_no_warning(self):
        issues = lint_cadquery_code(VALID_SIMPLE)
        assert "missing_import" not in _checks(issues)


class TestMissingExport:
    def test_missing_export_is_error(self):
        code = """\
import cadquery as cq
OUTPUT_PATH = "output.stl"
result = cq.Workplane("XY").box(10, 10, 10)
"""
        issues = lint_cadquery_code(code)
        assert "missing_export" in _checks(issues)
        export_issue = next(i for i in issues if i.check == "missing_export")
        assert export_issue.severity == "ERROR"

    def test_present_export_no_error(self):
        issues = lint_cadquery_code(VALID_SIMPLE)
        assert "missing_export" not in _checks(issues)

    def test_hardcoded_path_is_warning(self):
        code = """\
import cadquery as cq
result = cq.Workplane("XY").box(10, 10, 10)
cq.exporters.export(result, "output.stl")
"""
        issues = lint_cadquery_code(code)
        # export present, but no OUTPUT_PATH → warning
        assert "hardcoded_path" in _checks(issues)
        hw = next(i for i in issues if i.check == "hardcoded_path")
        assert hw.severity == "WARNING"


class TestModularStructure:
    def test_modular_without_assemble_is_error(self):
        code = """\
import cadquery as cq
OUTPUT_PATH = "output.stl"

def make_base():
    return cq.Workplane("XY").box(10, 10, 10)

result = make_base()
cq.exporters.export(result, OUTPUT_PATH)
"""
        issues = lint_cadquery_code(code)
        assert "missing_assemble" in _checks(issues)
        ma = next(i for i in issues if i.check == "missing_assemble")
        assert ma.severity == "ERROR"

    def test_assemble_defined_but_not_called_is_error(self):
        code = """\
import cadquery as cq
OUTPUT_PATH = "output.stl"

def make_base():
    return cq.Workplane("XY").box(10, 10, 10)

def assemble():
    return make_base()

cq.exporters.export(make_base(), OUTPUT_PATH)
"""
        issues = lint_cadquery_code(code)
        assert "missing_assemble_call" in _checks(issues)

    def test_valid_modular_no_errors(self):
        issues = lint_cadquery_code(VALID_MODULAR)
        errors = _errors(issues)
        assert not errors, f"Unexpected errors in valid modular code: {errors}"


class TestUncapturedBooleans:
    def test_uncaptured_union_is_error(self):
        code = """\
import cadquery as cq
OUTPUT_PATH = "output.stl"
result = cq.Workplane("XY").box(10, 10, 10)
result.union(cq.Workplane("XY").box(5, 5, 5))
cq.exporters.export(result, OUTPUT_PATH)
"""
        issues = lint_cadquery_code(code)
        assert "uncaptured_boolean" in _checks(issues)
        ub = next(i for i in issues if i.check == "uncaptured_boolean")
        assert ub.severity == "ERROR"

    def test_captured_union_no_error(self):
        code = """\
import cadquery as cq
OUTPUT_PATH = "output.stl"
result = cq.Workplane("XY").box(10, 10, 10)
result = result.union(cq.Workplane("XY").box(5, 5, 5)).clean()
cq.exporters.export(result, OUTPUT_PATH)
"""
        issues = lint_cadquery_code(code)
        assert "uncaptured_boolean" not in _checks(issues)


class TestHasErrors:
    def test_returns_true_for_errors(self):
        issues = [LintIssue("ERROR", "test", "msg")]
        assert has_errors(issues) is True

    def test_returns_false_for_warnings_only(self):
        issues = [LintIssue("WARNING", "test", "msg")]
        assert has_errors(issues) is False

    def test_returns_false_for_empty(self):
        assert has_errors([]) is False


class TestFormatLintIssues:
    def test_format_includes_severity(self):
        issues = [
            LintIssue("ERROR", "missing_export", "No export call found"),
            LintIssue("WARNING", "missing_import", "No import found"),
        ]
        text = format_lint_issues(issues)
        assert "[ERROR]" in text
        assert "[WARNING]" in text
        assert "missing_export" in text

    def test_format_includes_line_number(self):
        issues = [LintIssue("ERROR", "uncaptured_boolean", "result not captured", line=7)]
        text = format_lint_issues(issues)
        assert "line 7" in text
