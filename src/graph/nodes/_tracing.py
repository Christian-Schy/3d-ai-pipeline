"""Trace dict builder for agent_traces — extracted from nodes.py."""
import time


def _make_trace(
    agent: str,
    step: int,
    input_data,
    output_data,
    start_time: float,
    model: str = None,
    rag_chunks_used: list = None,
    error_tag: str = None,
    error_note: str = None,
    revision: bool = False,
) -> dict:
    """Build one agent_traces entry."""
    trace: dict = {
        "agent": agent,
        "step": step,
        "revision": revision,
        "input": input_data,
        "output": output_data,
        "rag_chunks_used": rag_chunks_used if rag_chunks_used is not None else [],
        "duration_ms": int((time.time() - start_time) * 1000),
    }
    if model is not None:
        trace["model"] = model
    if error_tag is not None:
        trace["error_tag"] = error_tag
    if error_note is not None:
        trace["error_note"] = error_note
    return trace
