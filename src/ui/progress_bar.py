"""
src/ui/progress_bar.py — Visual pipeline stage indicator for Gradio.

Renders as gr.HTML — updates on each node_* log line.

Stages:
  0 = idle
  1 = Interpreter
  2 = Planner
  3 = Coder
  4 = Executor
  5 = Validator
  6 = Done / Error
"""

STAGES = [
    "🔍 Interpreter",
    "📐 Planner",
    "💻 Coder",
    "⚙️  Executor",
    "✅ Validator",
]

# Map log keys → stage index (1-based)
LOG_TO_STAGE: dict[str, int] = {
    "node_interpreter": 1,
    "node_planner":     2,
    "node_coder":       3,
    "node_executor":    4,
    "node_validator":   5,
}


def build_progress_html(stage: int, error: bool = False) -> str:
    """Return HTML string for the pipeline progress bar.

    Args:
        stage:  0 = idle, 1-5 = active stage, 6 = done
        error:  if True, active stage is shown in red
    """
    if stage == 0:
        return _render(active=-1, done_up_to=-1, error=False)
    if stage >= 6:
        return _render(active=-1, done_up_to=4, error=error)
    return _render(active=stage - 1, done_up_to=stage - 2, error=error)


def _render(active: int, done_up_to: int, error: bool) -> str:
    items = []
    for i, label in enumerate(STAGES):
        if i <= done_up_to:
            cls = "stage done"
            icon = "✓"
        elif i == active:
            cls = "stage error" if error else "stage active"
            icon = "✕" if error else "⟳"
        else:
            cls = "stage pending"
            icon = "○"
        items.append(
            f'<div class="{cls}">'
            f'  <span class="icon">{icon}</span>'
            f'  <span class="label">{label}</span>'
            f'</div>'
        )

    connector = '<div class="connector"></div>'
    inner = connector.join(items)

    return f"""
<style>
  .pipeline-bar {{
    display: flex;
    align-items: center;
    gap: 0;
    padding: 8px 4px;
    font-family: system-ui, sans-serif;
    font-size: 12px;
  }}
  .stage {{
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 4px 10px;
    border-radius: 6px;
    white-space: nowrap;
    transition: background 0.2s;
  }}
  .stage.done    {{ background: #1a3a1a; color: #4caf50; }}
  .stage.active  {{ background: #1a2a3a; color: #64b5f6;
                    box-shadow: 0 0 6px rgba(100,181,246,0.4); }}
  .stage.error   {{ background: #3a1a1a; color: #ef5350; }}
  .stage.pending {{ background: transparent; color: #555; }}
  .icon {{ font-size: 13px; }}
  .connector {{
    width: 18px; height: 2px;
    background: #333;
    flex-shrink: 0;
  }}
</style>
<div class="pipeline-bar">{inner}</div>
"""
