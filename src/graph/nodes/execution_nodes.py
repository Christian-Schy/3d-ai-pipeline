"""Execution nodes: coder_node, code_fixer_node, code_review_node, executor_node."""
from __future__ import annotations
import os
import hashlib
import time
import structlog

from src.graph.state import PipelineState
from src.agents.coder import CoderAgent
from src.agents.code_fixer import CodeFixerAgent
from src.agents.code_review import CodeReviewAgent
from src.tools.sandbox import Sandbox
from ._registry import get_agent, get_raw_response
from ._tracing import _make_trace

log = structlog.get_logger()

STL_OUTPUT_DIR = "data/output"
os.makedirs(STL_OUTPUT_DIR, exist_ok=True)


def _get_sandbox() -> Sandbox:
    """Return a singleton Sandbox instance."""
    return get_agent.__wrapped__(Sandbox) if hasattr(get_agent, '__wrapped__') else _sandbox_singleton()


# Sandbox needs different singleton handling since it takes a timeout argument
_sandbox_instance = None

def _get_sandbox_instance() -> Sandbox:
    global _sandbox_instance
    if _sandbox_instance is None:
        _sandbox_instance = Sandbox(timeout=60)
    return _sandbox_instance


def coder_node(state: PipelineState) -> dict:
    """Generate or fix CadQuery code.

    Phase 1: Coder uses error message alone.
    Phase 2: Coder also reads fix_plan from CodeFixer.
    """
    _revision = state.get("attempts", 0) > 0
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1
    _coder = get_agent(CoderAgent)
    result = _coder.run(state)
    from src.config.loader import get_config as _gc
    _raw = getattr(getattr(_coder, "_rag", None), "last_chunks_used", [])
    _rag_chunks = _raw if isinstance(_raw, list) else []
    _trace = _make_trace(
        agent="coder", step=_step,
        input_data={
            "blueprint": state.get("blueprint", {}),
            "execution_error": state.get("execution_error", ""),
            "fix_plan": state.get("fix_plan", ""),
        },
        output_data=result.get("code", ""),
        start_time=_t0, model=_gc().models.coder,
        revision=_revision, rag_chunks_used=_rag_chunks,
        raw_response=get_raw_response(CoderAgent),
    )
    result["agent_traces"] = [_trace]
    return result


def code_fixer_node(state: PipelineState) -> dict:
    """Phase 2: diagnose repeated failures and write a fix plan for Coder.

    Only reached after 2+ failed Coder attempts.
    Writes fix_plan to state — Coder reads it on its next attempt.
    """
    log.info("node_code_fixer", attempts=state.get("attempts", 0))
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1
    result = get_agent(CodeFixerAgent).diagnose(state)
    from src.config.loader import get_config as _gc
    _trace = _make_trace(
        agent="code_fixer", step=_step,
        input_data={"execution_error": state.get("execution_error", ""),
                    "code": state.get("code", "")[:200]},
        output_data={"fix_plan": result.get("fix_plan", "")},
        start_time=_t0, model=_gc().models.code_fixer,
        raw_response=get_raw_response(CodeFixerAgent),
    )
    result["agent_traces"] = [_trace]
    return result


def code_review_node(state: PipelineState) -> dict:
    """Static code review: checks generated code against the blueprint.

    Runs between Coder and Executor. First runs the deterministic linter
    (syntax, export, modular structure, uncaptured booleans). If the linter
    finds ERRORs, returns immediately without LLM cost.

    On ERROR → routes back to Coder with specific fix instructions.
    On WARNING / PASS → continues to Executor.
    """
    _t0 = time.time()
    _step = len(state.get("agent_traces", [])) + 1
    code = state.get("code", "")

    if not code:
        log.warning("node_code_review_no_code")
        return {"code_review_approved": True, "code_review_issues": ""}

    log.info("node_code_review",
             code_lines=code.count("\n") + 1,
             attempt=state.get("attempts", 0))

    # ── Fast deterministic linter (no LLM) ───────────────────────────
    try:
        from src.tools.cq_linter import lint_cadquery_code, format_lint_issues, has_errors
        lint_issues = lint_cadquery_code(code)
        if has_errors(lint_issues):
            issues_text = format_lint_issues(lint_issues)
            log.warning("node_code_review_lint_fail",
                        errors=sum(1 for i in lint_issues if i.severity == "ERROR"),
                        warnings=sum(1 for i in lint_issues if i.severity == "WARNING"))
            _trace = _make_trace(
                agent="code_review", step=_step,
                input_data={"code_lines": code.count("\n") + 1, "source": "linter"},
                output_data={"approved": False, "issues": issues_text[:200]},
                start_time=_t0,
            )
            return {
                "code_review_approved": False,
                "code_review_issues": issues_text,
                "code_review_attempts": state.get("code_review_attempts", 0) + 1,
                "agent_traces": [_trace],
            }
        elif lint_issues:
            log.info("node_code_review_lint_warnings",
                     warnings=len(lint_issues))
    except Exception as _lint_err:
        log.warning("node_code_review_lint_error", error=str(_lint_err))

    result = get_agent(CodeReviewAgent).review(state)

    # Increment attempt counter so route_after_code_review can enforce max_retries
    result["code_review_attempts"] = state.get("code_review_attempts", 0) + 1

    from src.config.loader import get_config as _gc
    _trace = _make_trace(
        agent="code_review", step=_step,
        input_data={"code_lines": code.count("\n") + 1,
                    "blueprint_features": list(
                        state.get("blueprint", {}).get("features", {}).keys()
                    )},
        output_data={"approved": result.get("code_review_approved", True),
                     "issues": result.get("code_review_issues", "")[:200]},
        start_time=_t0, model=_gc().models.plan_validator,
        raw_response=get_raw_response(CodeReviewAgent),
    )
    result["agent_traces"] = [_trace]
    return result


def executor_node(state: PipelineState) -> dict:
    """Run the code in the sandbox and validate the resulting STL geometry."""
    code = state.get("code", "")
    description = state.get("description", "model")
    attempt = state.get("attempts", 0)

    safe_name = hashlib.md5(f"{description}_{attempt}".encode()).hexdigest()[:8]
    output_path = os.path.join(STL_OUTPUT_DIR, f"model_{safe_name}.stl")

    log.info("node_executor", output_path=output_path, attempt=attempt)

    _t0 = time.time()
    _step_exec = len(state.get("agent_traces", [])) + 1
    result = _get_sandbox_instance().run(code=code, output_path=output_path)

    if result.success:
        # Extract geometry state for the Planner/PromptAssembler to use on next modification
        from src.graph.geometry_state import extract_geometry_state
        geo = extract_geometry_state(output_path)

        _exec_trace = _make_trace(
            agent="executor", step=_step_exec,
            input_data=code[:200],
            output_data={"success": True, "volume": geo.volume,
                         "bbox": [geo.total_width, geo.total_depth, geo.total_height]},
            start_time=_t0,
        )

        # Run deterministic geometry precheck — gives LLM-Validator trustworthy context
        precheck_report = ""
        _precheck_traces: list = []
        try:
            from src.tools.geometry_precheck import run_geometry_precheck
            blueprint = state.get("blueprint", {})
            spec = state.get("specification") or state.get("description", "")
            if blueprint and spec and geo.volume > 0:
                _t1 = time.time()
                report = run_geometry_precheck(
                    blueprint=blueprint,
                    specification=spec,
                    volume_actual=geo.volume,
                    is_watertight=True,  # sandbox already validated geometry
                    bbox_dims=(geo.total_width, geo.total_depth, geo.total_height),
                )
                precheck_report = report.to_validator_context()
                log.info("executor_precheck_done", summary=report.summary,
                         critical=report.has_critical_issues)
                _precheck_traces.append(_make_trace(
                    agent="geometry_precheck", step=_step_exec + 1,
                    input_data={"blueprint": blueprint,
                                "volume": geo.volume,
                                "bbox": [geo.total_width, geo.total_depth, geo.total_height]},
                    output_data={"issues": len(report.feature_checks),
                                 "summary": report.summary,
                                 "has_critical": report.has_critical_issues},
                    start_time=_t1,
                ))
        except Exception as _precheck_err:
            log.warning("executor_precheck_failed", error=str(_precheck_err))

        return {
            "stl_path": output_path,
            "execution_error": "",
            "validation_error": "",
            "geometry_state": geo.model_dump(),
            "geometry_precheck_report": precheck_report,
            "agent_traces": [_exec_trace] + _precheck_traces,
        }
    else:
        error_msg = result.error
        is_geometry_error = "STL geometry invalid" in error_msg

        # Progressive build: identify the failing function when modular code fails
        progressive_info = ""
        if not is_geometry_error and "def assemble(" in code:
            blueprint = state.get("blueprint", {})
            try:
                from src.tools.progressive_build import run_progressive_build, format_progressive_error
                pb_result = run_progressive_build(
                    code=code,
                    blueprint=blueprint,
                    sandbox=_get_sandbox_instance(),
                    base_output_path=output_path,
                )
                if pb_result.get("failing_function"):
                    progressive_info = format_progressive_error(pb_result)
                    log.info("executor_progressive_build_done",
                             failing_function=pb_result["failing_function"],
                             step=pb_result["step"])
            except Exception as _pb_err:
                log.warning("executor_progressive_build_failed", error=str(_pb_err))

        final_error = progressive_info if progressive_info else error_msg

        _exec_trace = _make_trace(
            agent="executor", step=_step_exec,
            input_data=code[:200],
            output_data={"success": False, "error": final_error[:200],
                         "progressive": bool(progressive_info)},
            start_time=_t0,
            error_tag="syntax_error" if not is_geometry_error else "geometry_error",
        )
        return {
            "stl_path": "",
            "execution_error": "" if is_geometry_error else final_error,
            "validation_error": error_msg if is_geometry_error else "",
            "agent_traces": [_exec_trace],
        }
