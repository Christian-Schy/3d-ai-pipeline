"""
src/tools/session_store.py — Persists SessionState history across app restarts.

Saves to data/sessions/session.json on every push_to_history().
Loads on app start so history survives restarts.

Only history is persisted — runner, events, locks are runtime-only.
STL paths are stored as-is; if the file was deleted the entry is skipped on load.
"""

import json
from pathlib import Path

import structlog

log = structlog.get_logger()

SESSION_FILE = Path("data/sessions/session.json")


def save_history(history: list[dict]) -> None:
    """Persist history list to disk.

    history entries: {"label": str, "state": PipelineState dict}
    We only save fields needed to restore the UI — not the full heavy state.
    """
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)

    slim = []
    for entry in history:
        state = entry.get("state", {})
        # Only persist what's needed to restore the Result tab
        slim.append({
            "label": entry["label"],
            "run_id": entry.get("run_id", ""),
            "state": {
                "description":      state.get("description", ""),
                "specification":    state.get("specification", ""),
                "blueprint":        state.get("blueprint", {}),
                "code":             state.get("code", ""),
                "stl_path":         state.get("stl_path", ""),
                "validator_stats":  state.get("validator_stats", {}),
                "modification":     state.get("modification", ""),
                "agent_traces":     state.get("agent_traces", []),
            }
        })

    try:
        SESSION_FILE.write_text(
            json.dumps(slim, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        log.info("session_saved", entries=len(slim))
    except Exception as e:
        log.error("session_save_failed", error=str(e))


def load_history() -> list[dict]:
    """Load history from disk. Returns [] if file missing or corrupt.

    Skips entries where the STL file no longer exists.
    """
    if not SESSION_FILE.exists():
        return []

    try:
        data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("session_load_failed", error=str(e))
        return []

    history = []
    for entry in data:
        stl = entry.get("state", {}).get("stl_path", "")
        if stl and not Path(stl).exists():
            log.info("session_skip_missing_stl", stl=stl)
            continue
        history.append(entry)

    log.info("session_loaded", entries=len(history))
    return history
