"""Visioner node — image analysis before Interpreter."""
from __future__ import annotations
import structlog

from src.graph.state import PipelineState

log = structlog.get_logger()

_visioner = None


def _get_visioner():
    global _visioner
    if _visioner is None:
        from src.agents.visioner import VisionerAgent
        _visioner = VisionerAgent()
    return _visioner


def visioner_node(state: PipelineState) -> dict:
    """Run VisionerAgent to extract a partial spec from an image."""
    log.info("node_visioner", image_path=state.get("image_path", ""))
    return _get_visioner().run(state)
