"""
src/tools/session_logger.py — Logs every pipeline run for future LoRA training.

Each run is appended as one JSON line to data/sessions/runs.jsonl.
Format is designed for DPO training (Stufe 13):
  - good pairs: feedback="good" runs
  - bad pairs:  feedback="bad" runs or failed runs

Usage:
    logger = SessionLogger()
    logger.log_run(state, feedback="good")

JSONL format (one line per run):
{
  "run_id": "abc12345",
  "timestamp": "2026-03-09T...",
  "description": "30mm Würfel mit Bohrung",
  "specification": "Rectangular box 30x30x30mm...",
  "blueprint": {...},
  "code": "result = cq.Workplane...",
  "stl_path": "/tmp/...",
  "attempts": 1,
  "feedback": "good",   # "good" / "bad" / "" (no feedback yet)
  "success": true,
  "stats": {"size_mm": [30,30,30], "volume_mm3": 24000}
}
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import structlog

log = structlog.get_logger()

# Absolute path anchored to project root (2 levels up from src/tools/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SESSIONS_DIR = _PROJECT_ROOT / "data" / "sessions"
RUNS_FILE = SESSIONS_DIR / "runs.jsonl"

# Standardized error tags per agent — used for DPO labeling
ERROR_TAGS = {
    "interpreter": [
        "depth_lost",           # Tiefenangabe verschluckt
        "feature_missing",      # Feature komplett vergessen
        "position_wrong_axis",  # Z-Referenz als XY interpretiert
        "hallucinated_feature", # Feature erfunden das User nicht wollte
        "ambiguity_not_asked",  # Hätte nachfragen sollen
    ],
    "planner": [
        "depth_null_wrong",     # depth=null statt explizitem Wert
        "feature_dropped",      # Feature aus Spec nicht im Blueprint
        "wrong_dimensions",     # Maße falsch berechnet
        "bad_csg_order",        # Boolesche Reihenfolge falsch
        "position_calc_wrong",  # Positionsberechnung falsch
    ],
    "coder": [
        "syntax_error",         # CadQuery Syntax falsch
        "wrong_method",         # cutThruAll statt cutBlind etc.
        "feature_not_coded",    # Blueprint-Feature nicht implementiert
        "position_offset",      # center() falsch berechnet
        "workplane_wrong",      # Falsche Face-Selektion
    ],
    "validator": [
        "false_positive",       # Meldet Fehler wo keiner ist
        "false_negative",       # Übersieht echten Fehler
        "wrong_diagnosis",      # Fehler erkannt aber falsche Ursache
    ],
}


class SessionLogger:
    """Appends pipeline runs to a JSONL file for training data collection.

    Thread-safe via file append (each write is atomic on Linux).
    """

    def __init__(self):
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        self.log = structlog.get_logger().bind(tool="session_logger")

    def log_run(self, state: dict, feedback: str = "", task_id: str = "") -> str:
        """Append a run to the JSONL log file.

        Args:
            state:    Final PipelineState after the run.
            feedback: "good", "bad", or "" (user hasn't rated yet).

        Returns:
            run_id — unique identifier for this entry.
        """
        run_id = uuid.uuid4().hex[:8]
        entry = {
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_input": state.get("raw_input") or state.get("modification") or state.get("description", ""),
            "description": state.get("description", ""),
            "specification": state.get("specification", ""),
            "blueprint": state.get("blueprint", {}),
            "code": state.get("code", ""),
            "stl_path": state.get("stl_path", ""),
            "attempts": state.get("attempts", 0),
            "feedback": feedback,
            "error_agent": None,
            "error_note": None,
            "task_id": task_id or "",
            "success": bool(state.get("stl_path")) and not state.get("validator_feedback"),
            "stats": state.get("validator_stats", {}),
            "modification": state.get("modification", ""),
            "agent_traces": state.get("agent_traces", []),
        }

        try:
            line = json.dumps(entry, ensure_ascii=False, default=str)
            with open(RUNS_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            self.log.info("session_logged", run_id=run_id, feedback=feedback,
                          success=entry["success"],
                          traces=len(entry.get("agent_traces", [])),
                          file=str(RUNS_FILE))
        except Exception as e:
            import traceback
            self.log.error("session_log_failed", error=str(e),
                           traceback=traceback.format_exc())

        return run_id

    def update_feedback(self, run_id: str, feedback: str,
                        error_agent: str = "", error_note: str = "") -> bool:
        """Update the feedback field for an existing run.

        Args:
            run_id:      The run to update.
            feedback:    "good" or "bad".
            error_agent: Name of the agent that caused the error (e.g. "planner").
                         Only written when non-empty.
            error_note:  Optional free-text note describing what went wrong.
                         Only written when non-empty.

        Rewrites the line in-place (reads all, rewrites file).
        Returns True if run_id was found and updated.
        """
        if not RUNS_FILE.exists():
            return False

        lines = RUNS_FILE.read_text(encoding="utf-8").splitlines()
        updated = False

        for i, line in enumerate(lines):
            try:
                entry = json.loads(line)
                if entry.get("run_id") == run_id:
                    entry["feedback"] = feedback
                    if error_agent:
                        entry["error_agent"] = error_agent.strip()
                    if error_note:
                        entry["error_note"] = error_note.strip()
                    lines[i] = json.dumps(entry, ensure_ascii=False)
                    updated = True
                    break
            except json.JSONDecodeError:
                continue

        if updated:
            RUNS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
            self.log.info("session_feedback_updated", run_id=run_id, feedback=feedback,
                          error_agent=error_agent, has_note=bool(error_note))

        return updated

    def get_stats(self) -> dict:
        """Return basic stats about logged runs."""
        if not RUNS_FILE.exists():
            return {"total": 0, "good": 0, "bad": 0, "unrated": 0, "success_rate": 0}

        total = good = bad = success = 0
        for line in RUNS_FILE.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
                total += 1
                if e.get("feedback") == "good": good += 1
                if e.get("feedback") == "bad": bad += 1
                if e.get("success"): success += 1
            except json.JSONDecodeError:
                continue

        return {
            "total": total,
            "good": good,
            "bad": bad,
            "unrated": total - good - bad,
            "success_rate": round(success / total * 100, 1) if total else 0,
        }


def load_sessions() -> list[dict]:
    """Load all sessions from the JSONL log file."""
    if not RUNS_FILE.exists():
        return []
    sessions = []
    for line in RUNS_FILE.read_text(encoding="utf-8").splitlines():
        try:
            sessions.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return sessions


def extract_training_pairs(
    sessions: list[dict],
    agent_name: str,
    only_successful: bool = True,
) -> list[dict]:
    """Extract input/output pairs for a specific agent from session logs.

    Args:
        sessions:        List of session dicts (from load_sessions()).
        agent_name:      Which agent to extract: "interpreter", "planner", "coder", etc.
        only_successful: If True, skip sessions where success=False.

    Returns:
        List of dicts with: input, output, run_success, error_tag, run_id.
    """
    pairs = []
    for session in sessions:
        if only_successful and not session.get("success"):
            continue
        for trace in session.get("agent_traces", []):
            if trace.get("agent") == agent_name:
                pairs.append({
                    "input": trace.get("input"),
                    "output": trace.get("output"),
                    "run_success": session.get("success"),
                    "error_tag": trace.get("error_tag"),
                    "run_id": session.get("run_id"),
                })
    return pairs
