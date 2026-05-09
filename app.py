"""
app.py — Gradio UI for the 3D-AI-Pipeline.

Architecture rule: this file contains ONLY UI logic.
  ✓ Calls pipeline.PipelineRunner
  ✗ No direct agent imports
  ✗ No model calls
  ✗ No file I/O except showing results

Tabs:
  Generate — progress bar, chat dialog, input field, feedback buttons
  Result   — 3D preview + STL download
  Dev      — live logs, blueprint JSON, generated code, timing

Threading model:
  The pipeline blocks until complete (can take 30-120 seconds).
  We run it in a background thread and stream log output via a Queue
  into the Gradio log component using a generator function.
"""

import os
import queue
import threading
import time
import json
import structlog
import gradio as gr

from src.graph.pipeline import PipelineRunner
from src.graph.run_status import failure_reason, is_successful_state
from src.tools.transcriber import Transcriber
from src.tools.session_logger import SessionLogger
from src.tools.session_store import save_history, load_history
from src.ui.stl_viewer_html import stl_to_iframe_html
from src.ui.system_gauges import build_gauges_html
from src.ui.progress_bar import build_progress_html, LOG_TO_STAGE

_session_logger = SessionLogger()

# ------------------------------------------------------------------
# Logging bridge: structlog → Gradio textbox
# ------------------------------------------------------------------

_log_queue: queue.Queue = queue.Queue()


class GradioLogProcessor:
    """structlog processor that copies log lines into the UI queue."""

    def __call__(self, logger, method, event_dict):
        line = f"[{event_dict.get('agent', event_dict.get('event', ''))}] " \
               f"{event_dict.get('event', '')} " \
               f"{' '.join(f'{k}={v}' for k, v in event_dict.items() if k not in ('event', 'agent', '_record'))}"
        _log_queue.put(line.strip())
        return event_dict


structlog.configure(
    processors=[
        GradioLogProcessor(),
        structlog.dev.ConsoleRenderer(),
    ]
)

# ------------------------------------------------------------------
# Pipeline state shared between UI callbacks
# ------------------------------------------------------------------

class SessionState:
    """Holds pipeline state for one user session."""

    MAX_HISTORY = 10

    def __init__(self):
        self.runner = PipelineRunner()
        self.last_result = None
        self.pending_question = None
        self.answer_event = threading.Event()
        self.user_answer = ""
        self.is_running = False
        self.last_run_id: str = ""
        self.task_id: str = ""
        self.history: list[dict] = load_history()
        self._needs_streaming = False
        self.chat_messages: list[dict] = []   # shown in chat dialog
        self._seen_chat_keys: set[tuple] = set()  # dedup within a run

    def reset_for_new_run(self):
        self.pending_question = None
        self.answer_event.clear()
        self.user_answer = ""
        self.is_running = True
        self._needs_streaming = True
        self.chat_messages = []
        self._seen_chat_keys = set()

    def provide_answer(self, answer: str):
        self.user_answer = answer
        self.answer_event.set()

    def push_chat(self, msg: dict):
        """Add a chat message, deduplicating consecutive same-content from same agent."""
        key = (msg.get("name", ""), msg.get("content", ""))
        if key in self._seen_chat_keys:
            return
        self._seen_chat_keys.add(key)
        self.chat_messages.append(msg)

    def push_to_history(self):
        state = self.last_result
        if not state or not state.get("stl_path"):
            return
        stl = state["stl_path"]
        if any(e["state"].get("stl_path") == stl for e in self.history):
            return
        label = state.get("description", "Model")[:60]
        # Store run_id for identification in history
        run_id = getattr(self, "last_run_id", "") or ""
        self.history.append({"label": label, "state": state, "run_id": run_id})
        if len(self.history) > self.MAX_HISTORY:
            self.history.pop(0)
        save_history(self.history)

    def get_history_choices(self) -> list[str]:
        choices = []
        for i, e in enumerate(reversed(self.history)):
            run_id = e.get("run_id", "")
            rid_str = f" ({run_id[:8]})" if run_id else ""
            choices.append(f"[{i + 1}]{rid_str} {e['label']}")
        return choices

    def restore(self, choice: str) -> dict | None:
        choices = self.get_history_choices()
        if choice not in choices:
            return None
        idx = len(self.history) - 1 - choices.index(choice)
        return self.history[idx]["state"]


_session = SessionState()


# ------------------------------------------------------------------
# Chat helpers
# ------------------------------------------------------------------

def build_chat_html(messages: list[dict]) -> str:
    """Render chat messages as styled HTML bubbles."""
    if not messages:
        return (
            '<div style="color:var(--body-text-color-subdued,#888);padding:28px 16px;'
            'text-align:center;font-style:italic;font-size:13px;">'
            'Your conversation with the AI will appear here…</div>'
        )

    import html as _html

    parts = [
        '<div style="display:flex;flex-direction:column;gap:10px;padding:12px;">'
    ]

    for msg in messages:
        role = msg.get("role", "agent")
        content = _html.escape(str(msg.get("content", "")))
        # preserve newlines
        content = content.replace("\n", "<br>")

        if role == "user":
            parts.append(
                '<div style="display:flex;justify-content:flex-end;margin-left:15%">'
                '<div style="background:#3b82f6;color:#fff;padding:9px 14px;'
                'border-radius:18px 18px 4px 18px;word-wrap:break-word;'
                'line-height:1.5;font-size:13px;">'
                f'{content}</div></div>'
            )

        elif role == "system":
            color = "#16a34a" if msg.get("success") else "#dc2626"
            parts.append(
                f'<div style="text-align:center;padding:6px 12px;color:{color};'
                f'font-weight:600;font-size:13px;">{content}</div>'
            )

        else:
            icon = msg.get("icon", "🤖")
            name = msg.get("name", "Agent")
            msg_type = msg.get("type", "agent")

            if msg_type == "question":
                bg = "rgba(124,58,237,0.12)"
                border = "1px solid rgba(124,58,237,0.35)"
                name_color = "#7c3aed"
            elif msg_type == "code":
                bg = "rgba(30,30,30,0.85)"
                border = "1px solid rgba(80,80,80,0.4)"
                name_color = "#a3e635"
            else:
                bg = "rgba(100,116,139,0.08)"
                border = "1px solid rgba(100,116,139,0.18)"
                name_color = "var(--body-text-color-subdued,#64748b)"

            if msg_type == "code":
                # Render as monospace code block
                parts.append(
                    '<div style="display:flex;justify-content:flex-start;margin-right:5%">'
                    f'<div style="background:{bg};border:{border};padding:8px 12px;'
                    f'border-radius:6px;word-wrap:break-word;line-height:1.5;max-width:95%;">'
                    f'<div style="font-size:10px;color:{name_color};margin-bottom:4px;'
                    f'font-weight:700;letter-spacing:0.3px;">{icon} {name}</div>'
                    f'<pre style="margin:0;font-size:11px;color:#d4d4d4;'
                    f'white-space:pre-wrap;word-break:break-all;">{content}</pre>'
                    f'</div></div>'
                )
            else:
                parts.append(
                    '<div style="display:flex;justify-content:flex-start;margin-right:15%">'
                    f'<div style="background:{bg};border:{border};padding:9px 14px;'
                    f'border-radius:18px 18px 18px 4px;word-wrap:break-word;line-height:1.5;">'
                    f'<div style="font-size:10px;color:{name_color};margin-bottom:3px;'
                    f'font-weight:700;letter-spacing:0.3px;">{icon} {name}</div>'
                    f'<div style="font-size:13px;">{content}</div>'
                    f'</div></div>'
                )

    parts.append('</div>')
    return ''.join(parts)


def _extract_val(line: str, key: str) -> str:
    """Extract value after 'key=' from a log line (takes rest of line)."""
    marker = f"{key}="
    if marker not in line:
        return ""
    return line.split(marker, 1)[1].strip()


def _chat_event_from_log(line: str) -> dict | None:
    """Parse a structlog line into a chat event dict, or None if not relevant."""

    # ── Rich content events (logged explicitly by agents) ─────────────

    # Interpreter: question being asked
    if "Waiting for user answer:" in line:
        q = line.split("Waiting for user answer:", 1)[1].strip()
        return {"role": "agent", "icon": "🤖", "name": "Interpreter",
                "content": q, "type": "question"}

    # Modification interpreter: understood what to change
    if "modification_interpreter_done" in line:
        change = _extract_val(line, "change")
        additive = "is_additive=True" in line or "is_additive= True" in line
        tag = " [additive]" if additive else ""
        return {"role": "agent", "icon": "🧠", "name": "Interpreter",
                "content": f"Modification understood{tag}:\n{change}", "type": "agent"}

    # Interpreter: specification ready
    if "interpreter_spec_done" in line:
        spec = _extract_val(line, "spec")
        return {"role": "agent", "icon": "🧠", "name": "Interpreter",
                "content": f"✓ Specification:\n{spec}", "type": "agent"}

    # Feature Tagger: features identified
    if "feature_tagger_done" in line:
        count = _extract_val(line, "features_count").split()[0] if "features_count=" in line else "?"
        task = _extract_val(line, "task_type").split()[0] if "task_type=" in line else ""
        detail = f" ({task})" if task else ""
        return {"role": "agent", "icon": "🏷️", "name": "Feature Tagger",
                "content": f"✓ {count} feature(s) identified{detail}", "type": "agent"}

    # Coordinate Validator: issues found
    if "node_coordinate_validator_failed" in line:
        errors = _extract_val(line, "errors").split()[0] if "errors=" in line else "?"
        return {"role": "agent", "icon": "📏", "name": "Coord. Validator",
                "content": f"⚠️ {errors} coordinate issue(s) — sending back to Planner", "type": "agent"}

    # Plan Validator: failed
    if "node_plan_validator_quick_fail" in line or (
        "plan_valid" in line and "False" in line and "node_plan_validator" not in line
    ):
        issues = _extract_val(line, "issues")
        if issues:
            return {"role": "agent", "icon": "📋", "name": "Plan Validator",
                    "content": f"⚠️ Plan issues: {issues[:120]}", "type": "agent"}

    # Code Review: issues found (sends back to Coder)
    if "code_review_failed" in line or (
        "code_review_approved" in line and "False" in line
    ):
        issues = _extract_val(line, "issues")
        return {"role": "agent", "icon": "🔎", "name": "Code Review",
                "content": f"⚠️ Code issues found — sending back to Coder\n{issues[:200]}" if issues
                else "⚠️ Code issues found — sending back to Coder", "type": "agent"}

    # Planner: blueprint done
    if "planner_done" in line:
        bp_compact = _extract_val(line, "blueprint_json")
        try:
            bp_pretty = json.dumps(json.loads(bp_compact), indent=2, ensure_ascii=False)
        except Exception:
            desc = _extract_val(line, "description")
            root = _extract_val(line, "root_type")
            bp_pretty = f"Blueprint ready — {desc} ({root})" if root else f"Blueprint ready — {desc}"
        return {"role": "agent", "icon": "📐", "name": "Planner",
                "content": bp_pretty, "type": "code"}

    # Coder: code preview (first 6 lines, ↵-encoded)
    if "coder_code_preview" in line:
        preview = _extract_val(line, "preview").replace("↵", "\n")
        return {"role": "agent", "icon": "💻", "name": "Coder",
                "content": preview, "type": "code"}

    # Coder: code generated / fixed (show line count — before preview fires)
    if "coder_generate_done" in line or "coder_fix_done" in line:
        n = _extract_val(line, "code_lines").split()[0] if "code_lines=" in line else "?"
        verb = "Fixed" if "fix" in line else "Generated"
        return {"role": "agent", "icon": "💻", "name": "Coder",
                "content": f"{verb} — {n} lines of code", "type": "agent"}

    # Validator: passed
    if "validator_ok" in line:
        stats = _extract_val(line, "stats")
        return {"role": "agent", "icon": "✅", "name": "Validator",
                "content": f"Geometry OK — {stats}" if stats else "Geometry OK", "type": "agent"}

    # Validator: semantic failure
    if "validator_semantic_fail" in line:
        feedback = _extract_val(line, "feedback")
        return {"role": "agent", "icon": "⚠️", "name": "Validator",
                "content": f"Semantic issue: {feedback}", "type": "agent"}

    # Validator: geometry failure
    if "validator_geometry_fail" in line:
        feedback = _extract_val(line, "feedback")
        return {"role": "agent", "icon": "❌", "name": "Validator",
                "content": f"Geometry error: {feedback}", "type": "agent"}

    # Error loop
    if "node_error_router" in line and "attempts=" in line:
        n = _extract_val(line, "attempts").split()[0]
        phase = ""
        if "phase=" in line:
            p = _extract_val(line, "phase").split()[0]
            phase = f" · phase {p}"
        return {"role": "agent", "icon": "🔄", "name": "Error Loop",
                "content": f"Attempt {n}{phase} — retrying…", "type": "agent"}

    # Feature Assigner: assignments done
    if "feature_assigner_done" in line:
        count = _extract_val(line, "assignments").split()[0] if "assignments=" in line else "?"
        return {"role": "agent", "icon": "🔗", "name": "Feature Assigner",
                "content": f"✓ {count} feature(s) assigned", "type": "agent"}

    # Agent Dispatcher: routing decision
    if "agent_dispatcher" in line and "active=" in line:
        active = _extract_val(line, "active")
        flags = _extract_val(line, "flags")
        parts = [f"Active: {active}"]
        if flags and flags != "[]":
            parts.append(f"Flags: {flags}")
        return {"role": "agent", "icon": "🔀", "name": "Dispatcher",
                "content": " · ".join(parts), "type": "agent"}

    # Feature Position Assigner done
    if "feature_position_done" in line:
        count = _extract_val(line, "features").split()[0] if "features=" in line else "?"
        return {"role": "agent", "icon": "📍", "name": "Feature Pos. Assigner",
                "content": f"✓ {count} position(s) assigned", "type": "agent"}

    # Part Position Assigner done
    if "part_position_done" in line:
        count = _extract_val(line, "features").split()[0] if "features=" in line else "?"
        return {"role": "agent", "icon": "📌", "name": "Part Pos. Assigner",
                "content": f"✓ {count} position(s) assigned", "type": "agent"}

    # Blueprint Assembler done
    if "blueprint_assembler_done" in line:
        count = _extract_val(line, "features").split()[0] if "features=" in line else "?"
        order = _extract_val(line, "build_order")
        content = f"✓ Blueprint assembled ({count} features)"
        if order:
            content += f"\nBuild order: {order}"
        return {"role": "agent", "icon": "🏗️", "name": "Blueprint Assembler",
                "content": content, "type": "agent"}

    # ── Status-only events ─────────────────────────────────────────────
    status_checks = [
        ("node_entry_router",          "🔀", "Router",            "Analyzing request type…"),
        ("node_interpreter",           "🧠", "Interpreter",       "Analyzing your request…"),
        ("node_feature_tagger",        "🏷️", "Feature Tagger",   "Identifying features…"),
        ("agent_dispatcher",           "🔀", "Dispatcher",        "Routing agents…"),
        ("node_feature_assigner",      "🔗", "Feature Assigner",  "Assigning features…"),
        ("node_feature_position",      "📍", "Feature Pos.",      "Assigning positions…"),
        ("node_part_position",         "📌", "Part Pos.",         "Assigning part positions…"),
        ("node_blueprint_assembler",   "🏗️", "Assembler",        "Assembling blueprint…"),
        ("node_planner",               "📐", "Planner",           "Building blueprint…"),
        ("node_coordinate_validator",  "📏", "Coord. Validator",  "Checking coordinates…"),
        ("node_plan_validator",        "📋", "Plan Validator",    "Validating plan…"),
        ("node_function_decomposer",   "🔩", "Decomposer",        "Decomposing into functions…"),
        ("coder_generate_start",       "💻", "Coder",             "Writing code…"),
        ("coder_fill_skeleton",        "💻", "Coder",             "Filling code skeleton…"),
        ("coder_fix_start",            "🔧", "Coder",             "Fixing previous attempt…"),
        ("node_code_review",           "🔎", "Code Review",       "Reviewing generated code…"),
        ("node_executor",              "⚙️", "Executor",          "Executing in sandbox…"),
        ("node_validator",             "🔍", "Validator",         "Checking geometry…"),
        ("node_code_fixer",            "🛠️", "CodeFixer",         "Diagnosing failure…"),
        ("node_visioner",              "👁️", "Visioner",          "Extracting spec from image…"),
    ]

    for key, icon, name, text in status_checks:
        if key in line:
            return {"role": "agent", "icon": icon, "name": name,
                    "content": text, "type": "agent"}

    return None


# ------------------------------------------------------------------
# Blueprint feature extraction
# ------------------------------------------------------------------

def _cylinders_in_cuts(node: dict, in_cut: bool = False) -> list[dict]:
    if not isinstance(node, dict):
        return []
    t = node.get("type", "")
    if t == "cut":
        return (
            _cylinders_in_cuts(node.get("target", {}), in_cut=False)
            + _cylinders_in_cuts(node.get("tool", {}), in_cut=True)
        )
    if t in ("union", "intersect"):
        return (
            _cylinders_in_cuts(node.get("target", {}), in_cut=in_cut)
            + _cylinders_in_cuts(node.get("tool", {}), in_cut=in_cut)
        )
    if t in ("fillet", "chamfer", "shell"):
        return _cylinders_in_cuts(node.get("child", {}), in_cut=in_cut)
    if t == "cylinder" and in_cut:
        return [node]
    return []


def _format_stats(result: dict) -> str:
    lines = []
    stats = result.get("validator_stats") or {}
    ext = stats.get("extents_mm")
    vol = stats.get("volume_mm3")
    dim_line = ""
    if ext:
        dim_line = f"X: {ext[0]} mm  ·  Y: {ext[1]} mm  ·  Z: {ext[2]} mm"
    if vol:
        vol_str = f"Vol: {vol:,.0f} mm³"
        dim_line = f"{dim_line}  |  {vol_str}" if dim_line else vol_str
    if dim_line:
        lines.append(dim_line)

    blueprint = result.get("blueprint") or {}

    # Feature Tree format
    if "build_order" in blueprint and "features" in blueprint:
        features = blueprint.get("features", {})
        build_order = blueprint.get("build_order", [])
        if build_order:
            feature_types = [
                features.get(fid, {}).get("type", fid)
                for fid in build_order
            ]
            lines.append("Features: " + "  ·  ".join(feature_types))
    else:
        # Legacy CSG-Tree format
        holes = _cylinders_in_cuts(blueprint.get("root", {}))
        if holes:
            hole_parts = []
            for h in holes:
                dia = round(h["radius"] * 2, 1)
                pos = h.get("position") or {}
                px, py = pos.get("x", 0), pos.get("y", 0)
                pos_str = f"({px:+.1f}, {py:+.1f})" if (px or py) else "center"
                hole_parts.append(f"⌀{dia} mm @ {pos_str}")
            lines.append("Holes: " + "  ·  ".join(hole_parts))

    return "\n".join(lines)


def _build_traces_html(traces: list[dict]) -> str:
    """Render agent_traces as collapsible HTML details elements."""
    if not traces:
        return '<p style="color:#888;font-size:12px;padding:8px;">No agent traces available.</p>'

    import html as _html

    AGENT_ICONS = {
        "interpreter": "🧠", "modification_interpreter": "🧠",
        # Blueprint Chain (current)
        "inventar": "📦",
        "position_extractor": "🗺️",
        "text_splitter": "✂️",
        "feature_definierer": "🔧",
        "normalizer": "📝",
        "platzierer": "📍",
        "assembly": "🏗️",
        # Resolver + Validators
        "blueprint_architect": "🏛️",  # legacy / modification path
        "blueprint_resolver": "⚖️",
        "coordinate_validator": "📏",
        "plan_validator": "📋",
        "function_decomposer": "🔩",
        # Codegen + Execution
        "coder": "💻", "code_review": "🔎",
        "executor": "⚙️", "geometry_precheck": "📐",
        "validator": "🔍", "code_fixer": "🛠️",
    }

    parts = ['<div style="font-family:monospace;font-size:12px;padding:4px 0;">']
    for trace in traces:
        agent = trace.get("agent", "unknown")
        model = trace.get("model", "")
        duration = trace.get("duration_ms", 0)
        revision = trace.get("revision", False)
        icon = AGENT_ICONS.get(agent, "🤖")

        duration_s = f"{duration / 1000:.1f}s" if duration else "—"
        model_str = f" ({model})" if model else ""
        revision_str = " ↻ Revision" if revision else ""

        out = trace.get("output", {})
        skip_str = ""
        if isinstance(out, dict) and out.get("skipped"):
            reason = out.get("reason", "")
            skip_str = f" · ⏭ skipped ({reason})" if reason else " · ⏭ skipped"

        title = (f"{icon} {agent.replace('_', ' ').title()}"
                 f"{revision_str}{skip_str}{model_str} — {duration_s}")

        inp = trace.get("input", {})
        raw = trace.get("raw_response", "")
        inp_str = _html.escape(
            json.dumps(inp, ensure_ascii=False, indent=2)[:2000]
            if isinstance(inp, dict) else str(inp)[:2000]
        )
        out_str = _html.escape(
            json.dumps(out, ensure_ascii=False, indent=2)[:2000]
            if isinstance(out, dict) else str(out)[:2000]
        )

        # Raw response section (collapsible, only if present)
        raw_section = ""
        if raw:
            raw_str = _html.escape(str(raw)[:5000])
            raw_section = (
                f'<details style="margin-top:6px;">'
                f'<summary style="cursor:pointer;color:#f59e0b;font-size:10px;">'
                f'Raw LLM Response ({len(raw)} chars)</summary>'
                f'<pre style="background:rgba(0,0,0,0.4);padding:6px;border-radius:3px;'
                f'overflow-x:auto;white-space:pre-wrap;word-break:break-all;'
                f'font-size:11px;max-height:400px;overflow-y:auto;'
                f'border:1px solid rgba(245,158,11,0.3);">{raw_str}</pre>'
                f'</details>'
            )

        parts.append(
            f'<details style="margin:3px 0;border:1px solid rgba(100,116,139,0.2);'
            f'border-radius:4px;padding:4px 8px;">'
            f'<summary style="cursor:pointer;font-weight:600;padding:4px 0;user-select:none;">'
            f'{title}</summary>'
            f'<div style="margin-top:6px;">'
            f'<div style="color:#888;font-size:10px;margin-bottom:2px;">Input:</div>'
            f'<pre style="background:rgba(0,0,0,0.3);padding:6px;border-radius:3px;'
            f'overflow-x:auto;white-space:pre-wrap;word-break:break-all;'
            f'font-size:11px;max-height:200px;overflow-y:auto;">{inp_str}</pre>'
            f'<div style="color:#888;font-size:10px;margin:6px 0 2px;">Output:</div>'
            f'<pre style="background:rgba(0,0,0,0.3);padding:6px;border-radius:3px;'
            f'overflow-x:auto;white-space:pre-wrap;word-break:break-all;'
            f'font-size:11px;max-height:200px;overflow-y:auto;">{out_str}</pre>'
            f'{raw_section}'
            f'</div></details>'
        )

    parts.append('</div>')
    return ''.join(parts)


def _preload_rag():
    import threading
    def _load():
        try:
            from src.rag.base_rag import get_embed_fn
            get_embed_fn()
            _log_queue.put("[system] Embedding model ready.")
        except Exception as e:
            _log_queue.put(f"[system] Embedding preload failed: {e}")
    threading.Thread(target=_load, daemon=True).start()

_preload_rag()
_transcriber = Transcriber()
threading.Thread(target=_transcriber.preload, daemon=True).start()


# ------------------------------------------------------------------
# Pipeline runner with ask_user callback
# ------------------------------------------------------------------

def _ask_user_callback(question: str) -> str:
    _session.pending_question = question
    _log_queue.put(f"[interpreter] Waiting for user answer: {question}")
    _session.answer_event.wait()
    _session.answer_event.clear()
    return _session.user_answer


# ------------------------------------------------------------------
# Tab 1 — Generate
# ------------------------------------------------------------------

def on_transcribe(audio_path):
    btn_ready = gr.update(value="⚙ Generate", interactive=True)
    redo_show = gr.update(visible=True)
    if not audio_path:
        return gr.update(), btn_ready, gr.update(visible=False)
    text = _transcriber.transcribe(audio_path)
    if text:
        return gr.update(value=text), btn_ready, redo_show
    return gr.update(value="[Transkription fehlgeschlagen]"), btn_ready, redo_show


_PLACEHOLDER_GENERATE = "A 30mm cube with a centered M3 hole on top…\n(Enter = Generate  ·  Shift+Enter = new line)"
_PLACEHOLDER_MODIFY   = "Make the hole 2mm bigger / Add a chamfer…\n(Enter = Modify  ·  Shift+Enter = new line)"
_PLACEHOLDER_ANSWER   = "Type your answer here… (Enter to confirm)"


def on_unified_submit(text: str, image_path=None, task_id: str = ""):
    """Single handler for Generate, Modify, and Answer."""

    # ── Answer mode ──────────────────────────────────────────────────
    if _session.pending_question:
        _session._needs_streaming = False
        if text.strip():
            # Show the user answer in the chat
            _session.chat_messages.append({"role": "user", "content": text.strip()})
            _session.chat_messages.append({
                "role": "agent", "icon": "⏳", "name": "System",
                "content": "Resuming pipeline…", "type": "agent",
            })
            _session.provide_answer(text.strip())
            _session.pending_question = None
        return (
            gr.update(value=build_chat_html(_session.chat_messages)),  # chat_display
            gr.update(visible=False),    # question_row
            gr.update(interactive=False),
            gr.update(visible=False),    # new_model_btn
            gr.update(value=""),         # clear input
        )

    # ── Modify mode ──────────────────────────────────────────────────
    if _session.last_result:
        if not text.strip():
            return (
                gr.update(value=build_chat_html(_session.chat_messages)),
                gr.update(visible=False),
                gr.update(interactive=True),
                gr.update(visible=True),
                gr.update(),
            )
        _session.push_to_history()
        _session.reset_for_new_run()
        _session.chat_messages.append({"role": "user", "content": text.strip()})
        while not _log_queue.empty():
            _log_queue.get_nowait()
        previous = _session.last_result

        def run_modify():
            try:
                result = _session.runner.modify(
                    text,
                    previous_state=previous,
                    ask_user=_ask_user_callback,
                )
                _session.last_result = result
            except Exception as e:
                _session.last_result = None
                _log_queue.put(f"[error] Modification failed: {e}")
            finally:
                _session.is_running = False
                _log_queue.put("__DONE__")

        threading.Thread(target=run_modify, daemon=True).start()
        return (
            gr.update(value=build_chat_html(_session.chat_messages)),
            gr.update(visible=False),
            gr.update(interactive=False),
            gr.update(visible=False),
            gr.update(value=""),
        )

    # ── Generate mode ─────────────────────────────────────────────────
    if not text.strip() and not image_path:
        return (
            gr.update(value=build_chat_html(_session.chat_messages)),
            gr.update(visible=False),
            gr.update(interactive=True),
            gr.update(visible=False),
            gr.update(),
        )
    _session.task_id = (task_id or "").strip()
    _session.push_to_history()
    _session.reset_for_new_run()
    user_msg = text.strip() if text.strip() else "(Image uploaded)"
    _session.chat_messages.append({"role": "user", "content": user_msg})
    while not _log_queue.empty():
        _log_queue.get_nowait()

    def run_generate():
        try:
            result = _session.runner.run(
                text,
                ask_user=_ask_user_callback,
                image_path=image_path or "",
            )
            _session.last_result = result
        except Exception as e:
            _session.last_result = None
            _log_queue.put(f"[error] Pipeline crashed: {e}")
        finally:
            _session.is_running = False
            _log_queue.put("__DONE__")

    threading.Thread(target=run_generate, daemon=True).start()
    return (
        gr.update(value=build_chat_html(_session.chat_messages)),
        gr.update(visible=False),
        gr.update(interactive=False),
        gr.update(visible=False),
        gr.update(value=""),
    )


def on_new_model():
    """Reset session so next submit starts a fresh model."""
    _session.last_result = None
    _session.last_run_id = ""
    _session.chat_messages = []
    _session._seen_chat_keys = set()
    return (
        gr.update(value="⚙ Generate"),
        gr.update(visible=False),
        gr.update(placeholder=_PLACEHOLDER_GENERATE),
        gr.update(value=build_chat_html([])),  # clear chat
        gr.update(visible=False),              # agent_traces_accordion
        gr.update(value=""),                   # agent_traces_display
        gr.update(visible=False),              # error_feedback_row
    )


def stream_logs():
    """Generator: yields log lines as they arrive, updates UI when done."""
    if not _session._needs_streaming:
        return

    log_lines = []
    _nc = gr.update()
    current_stage = 0

    while True:
        try:
            line = _log_queue.get(timeout=0.2)
        except queue.Empty:
            # Waiting for user answer — show question in chat
            if _session.pending_question:
                q = _session.pending_question
                # Add question bubble to chat (once)
                already_asked = any(
                    m.get("type") == "question" and m.get("content") == q
                    for m in _session.chat_messages
                )
                if not already_asked:
                    _session.chat_messages.append({
                        "role": "agent", "icon": "🤖", "name": "Interpreter",
                        "content": q, "type": "question",
                    })

                yield (
                    "\n".join(log_lines),
                    gr.update(visible=False),   # question_row (hidden — shown in chat)
                    _nc,                         # question_label
                    gr.update(value=build_chat_html(_session.chat_messages)),  # chat
                    _nc, _nc, _nc, _nc,          # result_viewer, result_stats, blueprint, code
                    gr.update(interactive=True, value="↩ Answer"),
                    gr.update(visible=False),    # new_model_btn
                    _nc,                         # history_dropdown
                    gr.update(placeholder=_PLACEHOLDER_ANSWER),
                    _nc,                         # image_input
                    _nc, _nc, _nc,               # image_group, preview_group, inline_viewer
                    gr.update(value=build_progress_html(current_stage)),
                    gr.update(visible=False),    # agent_traces_accordion
                    _nc,                         # agent_traces_display
                    gr.update(visible=False),    # error_feedback_row
                )
            continue

        if line == "__DONE__":
            break

        # Update progress stage
        for key, stage in LOG_TO_STAGE.items():
            if key in line:
                current_stage = stage
                break

        # Parse into chat event
        event = _chat_event_from_log(line)
        if event:
            _session.push_chat(event)

        log_lines.append(line)
        yield (
            "\n".join(log_lines[-50:]),
            gr.update(visible=False),       # question_row
            _nc,                             # question_label
            gr.update(value=build_chat_html(_session.chat_messages)),  # chat
            _nc, _nc, _nc, _nc,              # result_viewer, result_stats, blueprint, code
            gr.update(interactive=False),    # submit_btn
            gr.update(visible=False),        # new_model_btn
            _nc,                             # history_dropdown
            _nc,                             # description_input
            _nc,                             # image_input
            _nc, _nc, _nc,                   # image_group, preview_group, inline_viewer
            gr.update(value=build_progress_html(current_stage)),
            _nc, _nc, _nc,                   # agent_traces_accordion, agent_traces_display, error_feedback_row
        )

    # Run finished
    result = _session.last_result
    success = is_successful_state(result)

    # Log the run immediately — before any further processing that could raise.
    if result:
        auto_feedback = "good" if success else "bad"
        _session.last_run_id = _session_logger.log_run(result, feedback=auto_feedback, task_id=_session.task_id)
    else:
        import logging as _logging
        _logging.warning("stream_logs: _session.last_result is None — run not logged")

    if success:
        stl = os.path.abspath(result["stl_path"])
        status_msg = f"✅ Model ready! ({result.get('attempts', 0)} attempt(s))"
        blueprint_text = json.dumps(result.get("blueprint", {}), indent=2)
        code_text = result.get("code", "")
        _session.push_to_history()
        history_choices = _session.get_history_choices()
        history_value = history_choices[0] if history_choices else None
    else:
        stl = None
        error = failure_reason(result) or "Unknown error"
        status_msg = f"❌ Failed: {error[:120]}"
        blueprint_text = ""
        code_text = ""
        history_choices = _session.get_history_choices()
        history_value = None

    # Add final status to chat
    _session.chat_messages.append({
        "role": "system",
        "content": status_msg,
        "success": success,
    })

    stats_text = _format_stats(_session.last_result or {}) if success else ""

    submit_label = "✏ Modify" if success else "⚙ Generate"
    input_placeholder = _PLACEHOLDER_MODIFY if success else _PLACEHOLDER_GENERATE

    traces_html = _build_traces_html(
        (_session.last_result or {}).get("agent_traces", [])
    )

    yield (
        "\n".join(log_lines),
        gr.update(visible=False),                      # question_row
        _nc,                                           # question_label
        gr.update(value=build_chat_html(_session.chat_messages)),  # chat
        gr.update(value=stl_to_iframe_html(stl)),      # result_viewer
        gr.update(value=stats_text),                   # result_stats
        gr.update(value=blueprint_text),               # blueprint_output
        gr.update(value=code_text),                    # code_output
        gr.update(interactive=True, value=submit_label),  # submit_btn
        gr.update(visible=success),                    # new_model_btn
        gr.update(choices=history_choices, value=history_value),  # history_dropdown
        gr.update(value="", placeholder=input_placeholder),  # description_input
        gr.update(value=None),                         # image_input
        gr.update(visible=not success),                # image_group
        gr.update(visible=success),                    # preview_group
        gr.update(value=stl_to_iframe_html(stl)),      # inline_viewer
        gr.update(value=build_progress_html(6, error=not success)),
        gr.update(visible=True),                       # agent_traces_accordion (always show)
        gr.update(value=traces_html),                  # agent_traces_display
        gr.update(visible=True),                       # error_feedback_row (always show)
    )


def on_select_error_agent(agent_choice: str) -> tuple:
    """When user selects an agent in the error feedback, show that agent's trace output."""
    if not agent_choice or not _session.last_result:
        return gr.update(visible=False), gr.update(value="")

    # Map radio label to agent name in traces
    # Reflects the active pipeline (3-Step Blueprint Chain + Multi-Part split).
    agent_map = {
        "Interpreter": "interpreter",
        "Inventar": "inventar",
        "Position-Extractor": "position_extractor",
        "Text-Splitter": "text_splitter",
        "Feature-Definierer": "feature_definierer",
        "Platzierer": "platzierer",
        "Assembly": "assembly",
        "Coder": "coder",
        "Plan-Validator": "plan_validator",
        "Validator": "validator",
    }
    agent_name = agent_map.get(agent_choice, "")
    traces = (_session.last_result or {}).get("agent_traces", [])

    # Filter traces for the selected agent
    agent_traces = [t for t in traces if t.get("agent") == agent_name]
    if not agent_traces:
        return gr.update(visible=True), gr.update(
            value=f'<p style="color:#888;padding:8px;">Kein Trace für {agent_choice} gefunden.</p>'
        )

    html = _build_traces_html(agent_traces)
    return gr.update(visible=True), gr.update(value=html)


def on_restore_history(choice: str):
    state = _session.restore(choice)
    if state is None:
        return (gr.update(),) * 11
    _session.last_result = state
    # Try to restore run_id from history entry
    choices = _session.get_history_choices()
    if choice in choices:
        idx = len(_session.history) - 1 - choices.index(choice)
        _session.last_run_id = _session.history[idx].get("run_id", "")
    stl = os.path.abspath(state["stl_path"]) if state.get("stl_path") else None
    stats_text = _format_stats(state)
    fig = stl_to_iframe_html(stl)
    desc = state.get("description", "")[:60]
    # Show restored model in chat
    restored_msgs = [
        {"role": "user", "content": desc},
        {"role": "system", "content": f"✅ Restored: {desc}", "success": True},
    ]
    traces_html = _build_traces_html(state.get("agent_traces", []))
    return (
        gr.update(value=fig),
        gr.update(value=stats_text),
        gr.update(value=json.dumps(state.get("blueprint", {}), indent=2)),
        gr.update(value=state.get("code", "")),
        gr.update(value=build_chat_html(restored_msgs)),   # chat_display
        gr.update(visible=False),
        gr.update(visible=True),
        gr.update(value=fig),
        gr.update(visible=True),              # agent_traces_accordion
        gr.update(value=traces_html),         # agent_traces_display
        gr.update(visible=True),              # error_feedback_row
    )


def on_thumb_good():
    if _session.last_run_id:
        _session_logger.update_feedback(_session.last_run_id, "good")
    return gr.update(value="Feedback gespeichert: 👍", visible=True)


def on_save_golden(slug: str) -> str:
    """Save current run as a golden regression test case."""
    if not _session.last_run_id:
        return "Kein aktiver Run — erst einen Run starten."
    slug = slug.strip().lower()
    slug = __import__("re").sub(r"[^a-z0-9]+", "_", slug).strip("_")[:60]
    if not slug:
        return "Bitte einen Slug eingeben (z.B. 'wuerfel_6_features')."
    from scripts.save_golden import save
    try:
        path = save(_session.last_run_id, slug, note="Gespeichert aus UI")
        return f"Golden Case gespeichert: {path.name}"
    except SystemExit as e:
        return f"Fehler: {e}"


def on_thumb_bad():
    if _session.last_run_id:
        _session_logger.update_feedback(_session.last_run_id, "bad", error_agent="", error_note="")
    return gr.update(value="Feedback gespeichert: 👎", visible=True)


def on_submit_error(error_agent: str, paired_run_id: str):
    """Save run as bad with error_agent and optional paired run."""
    if not error_agent:
        return (
            gr.update(value="⚠️ Bitte Agent auswählen", visible=True),
            gr.update(),
            gr.update(),
        )
    if not _session.last_run_id:
        return (
            gr.update(value="⚠️ Keine Run-ID — Fehler kann nicht gespeichert werden", visible=True),
            gr.update(),
            gr.update(),
        )
    _session_logger.update_feedback(
        _session.last_run_id, "bad",
        error_agent=error_agent.lower().replace("-", "_"),
        error_note="",
        paired_run_id=(paired_run_id or "").strip(),
    )
    pair_info = f" (Paar: {paired_run_id.strip()[:8]})" if paired_run_id and paired_run_id.strip() else ""
    return (
        gr.update(value=f"✅ Fehler gespeichert{pair_info}", visible=True),
        gr.update(value=None),  # clear radio
        gr.update(value=""),    # clear paired input
    )


# ------------------------------------------------------------------
# UI Layout
# ------------------------------------------------------------------

_UI_CSS = """
    /* Mic: hide waveform display, keep buttons visible */
    #mic-input .waveform-container { display: none !important; }
    #mic-input { min-height: 0 !important; padding: 4px !important; }
    #mic-input > .wrap { min-height: 0 !important; }
    /* Pulse animation on recording */
    #mic-input button[aria-label*="stop" i],
    #mic-input button.stop-button {
        animation: mic-pulse 1s ease-in-out infinite;
        background: #e53e3e !important;
    }
    @keyframes mic-pulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(229,62,62,0.5); }
        50%       { box-shadow: 0 0 0 8px rgba(229,62,62,0); }
    }
    /* Redo button: compact */
    #redo-btn { align-self: center; }
    /* Gauges: sticky */
    #gauges-col { position: sticky; top: 8px; }
    /* Chat box: fixed height, no layout shift */
    /* chat-col scrollbar styling */
    #chat-col::-webkit-scrollbar { width: 4px; }
    #chat-col::-webkit-scrollbar-thumb { background: rgba(100,116,139,0.3); border-radius: 2px; }
    /* Progress bar: no extra margin at top */
    .pipeline-bar { margin: 0 !important; padding: 6px 4px !important; }
"""

_UI_JS = """
() => {
    function initLogScroller() {
        const wrap = document.querySelector('#log-output');
        if (!wrap) { setTimeout(initLogScroller, 400); return; }
        const getTA = () => wrap.querySelector('textarea');
        setInterval(() => { const ta = getTA(); if (ta) ta.scrollTop = ta.scrollHeight; }, 300);
    }
    initLogScroller();

    function initChatScroller() {
        const chatCol = document.querySelector('#chat-col');
        if (!chatCol) { setTimeout(initChatScroller, 400); return; }
        // Find the scrollable container inside the component
        function getScrollable(el) {
            let cur = el;
            while (cur && cur !== document.body) {
                const s = window.getComputedStyle(cur);
                if (s.overflowY === 'auto' || s.overflowY === 'scroll') return cur;
                cur = cur.parentElement;
            }
            return chatCol;
        }
        let scrollable = null;
        const observer = new MutationObserver(() => {
            if (!scrollable) scrollable = getScrollable(chatCol);
            scrollable.scrollTop = scrollable.scrollHeight;
        });
        observer.observe(chatCol, { childList: true, subtree: true });
    }
    initChatScroller();
}
"""


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="3D-AI-Pipeline") as demo:
        gr.Markdown("# 🔧 3D-AI-Pipeline")
        gr.Markdown("Describe a 3D model in plain text — get a printable STL.")

        gauge_timer = gr.Timer(value=3)

        with gr.Tabs():

            # ---- Tab 1: Generate ----
            with gr.Tab("Generate"):

                # ── Progress bar — very top, full width ──────────────
                progress_bar = gr.HTML(value=build_progress_html(0))

                with gr.Row(equal_height=False):
                    # ── Main content ──────────────────────────────────
                    with gr.Column(scale=10):

                        # Top row: chat (left) + image/preview (right)
                        with gr.Row(equal_height=False):
                            with gr.Column(scale=3):
                                chat_display = gr.HTML(
                                    value=build_chat_html([]),
                                    label="",
                                    elem_id="chat-col",
                                    autoscroll=True,
                                    max_height=340,
                                )

                            with gr.Column(scale=4):
                                with gr.Group() as image_group:
                                    image_input = gr.Image(
                                        label="Image or sketch (optional)",
                                        type="filepath",
                                        height=340,
                                    )
                                with gr.Group(visible=False) as preview_group:
                                    inline_viewer = gr.HTML(value="", label="Current model")
                                    clear_preview_btn = gr.Button(
                                        "✕ Upload new image", size="sm", variant="secondary"
                                    )

                        # Bottom row: description (left) + task-id + generate + mic (right)
                        with gr.Row(equal_height=True):
                            description_input = gr.Textbox(
                                label="Model description",
                                placeholder=_PLACEHOLDER_GENERATE,
                                lines=4,
                                scale=5,
                            )
                            task_id_input = gr.Textbox(
                                label="Task-ID",
                                placeholder="z.B. 4",
                                lines=1,
                                max_lines=1,
                                scale=1,
                                min_width=80,
                            )
                            with gr.Column(scale=2, min_width=160):
                                submit_btn = gr.Button(
                                    "⚙ Generate", variant="primary", size="lg",
                                )
                                new_model_btn = gr.Button(
                                    "✓ Fertig — Nächstes Modell", variant="secondary",
                                    visible=False,
                                )
                                with gr.Row():
                                    audio_input = gr.Audio(
                                        sources=["microphone"],
                                        type="filepath",
                                        show_label=False,
                                        elem_id="mic-input",
                                        scale=3,
                                        min_width=60,
                                        waveform_options=gr.WaveformOptions(
                                            show_recording_waveform=False,
                                            sample_rate=16000,
                                        ),
                                    )
                                    redo_btn = gr.Button(
                                        "🔄", variant="secondary", scale=1, min_width=36,
                                        visible=False, elem_id="redo-btn",
                                    )

                        # ── Agent Traces accordion — appears after successful run ──
                        with gr.Accordion(
                            "Agent Responses", open=False, visible=False
                        ) as agent_traces_accordion:
                            agent_traces_display = gr.HTML(value="")

                        # ── Error feedback — appears after successful run ──
                        with gr.Row(visible=False) as error_feedback_row:
                            with gr.Column():
                                error_agent_radio = gr.Radio(
                                    choices=["Interpreter", "Inventar",
                                             "Position-Extractor", "Text-Splitter",
                                             "Feature-Definierer", "Platzierer",
                                             "Assembly", "Coder",
                                             "Plan-Validator", "Validator"],
                                    label="Fehler verursacht durch:",
                                    value=None,
                                )
                                # Agent output preview (shown when selecting an agent)
                                agent_output_preview = gr.HTML(
                                    value="", visible=False,
                                    label="Agent Output",
                                )
                                paired_run_input = gr.Textbox(
                                    label="Paar-Run-ID (good run)",
                                    placeholder="z.B. abc12345 — leer lassen wenn kein Paar",
                                    max_lines=1,
                                )
                                with gr.Row():
                                    save_error_btn = gr.Button(
                                        "Fehler speichern", variant="stop", scale=2,
                                    )
                                    error_status = gr.Markdown("", visible=False)

                        # ── Question row — hidden (questions shown in chat) ──
                        with gr.Row(visible=False) as question_row:
                            question_label = gr.Textbox(
                                label="Question from AI", interactive=False,
                            )

                        # ── History ───────────────────────────────────
                        gr.Markdown("---")
                        gr.Markdown("**Model History:**")
                        with gr.Row():
                            history_dropdown = gr.Dropdown(
                                label="Saved models (newest first)",
                                choices=[],
                                interactive=True,
                                scale=4,
                            )
                            restore_btn = gr.Button("↩ Restore", variant="secondary", scale=1)

                    # ── Gauges — right column ─────────────────────────
                    with gr.Column(scale=1, min_width=44, elem_id="gauges-col"):
                        gauges = gr.HTML(value=build_gauges_html(), label="")

            # ---- Tab 2: Result ----
            with gr.Tab("Result"):
                result_viewer = gr.HTML(value="", label="3D Preview")
                result_stats = gr.Textbox(label="Dimensions", interactive=False)
                download_btn = gr.File(label="Download STL")
                with gr.Row():
                    thumb_up   = gr.Button("👍", scale=1, variant="secondary")
                    thumb_down = gr.Button("👎", scale=1, variant="secondary")
                feedback_label = gr.Markdown("", visible=False)
                with gr.Row():
                    golden_slug = gr.Textbox(
                        placeholder="z.B. wuerfel_6_features",
                        label="Als Golden Test speichern (Slug)",
                        scale=4,
                        interactive=True,
                    )
                    save_golden_btn = gr.Button("Speichern", scale=1, variant="secondary")
                golden_status = gr.Markdown("", visible=False)

            # ---- Tab 3: Dev ----
            with gr.Tab("Dev"):
                log_output = gr.Textbox(
                    label="Live Logs",
                    lines=20, max_lines=20,
                    interactive=False, autoscroll=True,
                    elem_id="log-output",
                )
                with gr.Row():
                    blueprint_output = gr.Code(
                        label="Blueprint (CSG-Tree)", language="json", lines=15,
                    )
                    code_output = gr.Code(
                        label="Generated CadQuery Code", language="python", lines=15,
                    )

        # stream_logs outputs — 21 values
        _stream_outputs = [
            log_output, question_row, question_label,
            chat_display,
            result_viewer, result_stats, blueprint_output,
            code_output, submit_btn, new_model_btn, history_dropdown,
            description_input, image_input,
            image_group, preview_group, inline_viewer,
            progress_bar,
            agent_traces_accordion, agent_traces_display, error_feedback_row,
        ]

        # ---- Wiring ----
        audio_input.start_recording(
            fn=lambda: (gr.update(interactive=False, value="🎙 Transcribing…"), gr.update(visible=False)),
            outputs=[submit_btn, redo_btn],
        )
        audio_input.stop_recording(
            fn=on_transcribe,
            inputs=[audio_input],
            outputs=[description_input, submit_btn, redo_btn],
        )

        redo_btn.click(
            fn=lambda: (gr.update(value=""), gr.update(visible=False)),
            outputs=[description_input, redo_btn],
            js="""() => {
                const wrap = document.querySelector('#mic-input');
                if (!wrap) return [];
                const btns = [...wrap.querySelectorAll('button')];
                let found = false;
                for (const btn of btns) {
                    const lbl = (btn.getAttribute('aria-label') || btn.title || '').toLowerCase();
                    if (/clear|delete|remove|trash/.test(lbl)) {
                        btn.click(); found = true; break;
                    }
                }
                if (!found) {
                    for (let i = btns.length - 1; i >= 0; i--) {
                        const lbl = (btns[i].getAttribute('aria-label') || '').toLowerCase();
                        if (!/play|pause|volume|mute/.test(lbl)) {
                            btns[i].click(); break;
                        }
                    }
                }
                return [];
            }""",
        )
        audio_input.clear(
            fn=lambda: (gr.update(value=""), gr.update(visible=False)),
            outputs=[description_input, redo_btn],
        )

        _submit_chain = dict(
            fn=on_unified_submit,
            inputs=[description_input, image_input, task_id_input],
            outputs=[chat_display, question_row, submit_btn, new_model_btn, description_input],
        )
        submit_btn.click(**_submit_chain).then(
            fn=stream_logs, inputs=[], outputs=_stream_outputs,
        )
        description_input.submit(**_submit_chain).then(
            fn=stream_logs, inputs=[], outputs=_stream_outputs,
        )

        # Populate history dropdown from disk on startup
        demo.load(
            fn=lambda: gr.update(
                choices=_session.get_history_choices(),
                value=_session.get_history_choices()[0] if _session.history else None,
            ),
            outputs=[history_dropdown],
        )

        new_model_btn.click(
            fn=on_new_model,
            outputs=[submit_btn, new_model_btn, description_input, chat_display,
                     agent_traces_accordion, agent_traces_display, error_feedback_row],
        )

        restore_btn.click(
            fn=on_restore_history,
            inputs=[history_dropdown],
            outputs=[
                result_viewer, result_stats, blueprint_output, code_output,
                chat_display,    # ← was status_text
                image_group, preview_group, inline_viewer,
                agent_traces_accordion, agent_traces_display, error_feedback_row,
            ],
        )

        clear_preview_btn.click(
            fn=lambda: (
                gr.update(visible=True),
                gr.update(visible=False),
                gr.update(value=""),
            ),
            outputs=[image_group, preview_group, inline_viewer],
        )

        thumb_up.click(fn=on_thumb_good, outputs=[feedback_label])
        thumb_down.click(fn=on_thumb_bad, outputs=[feedback_label])

        save_error_btn.click(
            fn=on_submit_error,
            inputs=[error_agent_radio, paired_run_input],
            outputs=[error_status, error_agent_radio, paired_run_input],
        )

        # Show agent output when selecting an agent in error feedback
        error_agent_radio.change(
            fn=on_select_error_agent,
            inputs=[error_agent_radio],
            outputs=[agent_output_preview, agent_output_preview],
        )

        save_golden_btn.click(
            fn=on_save_golden,
            inputs=[golden_slug],
            outputs=[golden_status],
        ).then(fn=lambda msg: gr.update(value=msg, visible=True), inputs=[golden_status], outputs=[golden_status])

        gauge_timer.tick(fn=build_gauges_html, outputs=[gauges])

    return demo


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    ui = build_ui()
    ui.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        theme=gr.themes.Soft(),
        css=_UI_CSS,
        js=_UI_JS,
        allowed_paths=[os.path.abspath("data")],
    )
