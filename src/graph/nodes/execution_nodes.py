"""Execution nodes: coder_node, code_fixer_node, executor_node."""
from __future__ import annotations
import os
import hashlib
import time
import structlog

from src.graph.state import PipelineState
from src.agents.coder import CoderAgent
from src.agents.code_fixer import CodeFixerAgent
from src.tools.sandbox import Sandbox
from ._registry import get_agent
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
        _exec_trace = _make_trace(
            agent="executor", step=_step_exec,
            input_data=code[:200],
            output_data={"success": False, "error": error_msg[:200]},
            start_time=_t0,
            error_tag="syntax_error" if not is_geometry_error else "geometry_error",
        )
        return {
            "stl_path": "",
            "execution_error": "" if is_geometry_error else error_msg,
            "validation_error": error_msg if is_geometry_error else "",
            "agent_traces": [_exec_trace],
        }
