"""Printer node — dead code for now, kept available for Stufe 11."""
from __future__ import annotations
import structlog

from src.graph.state import PipelineState

log = structlog.get_logger()

_printer = None


def _get_printer():
    global _printer
    if _printer is None:
        from src.agents.printer import PrinterAgent
        _printer = PrinterAgent()
    return _printer


def printer_node(state: PipelineState) -> dict:
    """Slice STL and send to Bambu P1S for printing.

    Only triggered by explicit user action — never automatic.
    """
    stl_path = state.get("stl_path", "")
    description = state.get("description", "model")[:40]

    log.info("node_printer", stl_path=stl_path)

    result = _get_printer().print(
        stl_path=stl_path,
        task_name=description,
    )

    log.info("node_printer_done",
             success=result.get("success"),
             message=result.get("message", "")[:80])

    return {"print_status": result.get("message", "")}
