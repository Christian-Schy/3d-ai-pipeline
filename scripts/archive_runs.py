"""
scripts/archive_runs.py — Archiviert runs.jsonl und startet frisch.

Usage:
    python -m scripts.archive_runs

Verschiebt data/sessions/runs.jsonl → data/sessions/archive/runs_<datum>.jsonl
Legt eine leere runs.jsonl an.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSIONS_DIR = PROJECT_ROOT / "data" / "sessions"
RUNS_FILE = SESSIONS_DIR / "runs.jsonl"
ARCHIVE_DIR = SESSIONS_DIR / "archive"


def main():
    if not RUNS_FILE.exists():
        print("Keine runs.jsonl gefunden — nichts zu archivieren.")
        return

    count = sum(1 for line in RUNS_FILE.open() if line.strip())
    print(f"runs.jsonl enthält {count} Runs.")

    answer = input("Wirklich archivieren und neu starten? [j/N] ").strip().lower()
    if answer != "j":
        print("Abgebrochen.")
        sys.exit(0)

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
    archive_file = ARCHIVE_DIR / f"runs_{stamp}.jsonl"

    RUNS_FILE.rename(archive_file)
    RUNS_FILE.write_text("", encoding="utf-8")

    print(f"✓ Archiviert nach: {archive_file.relative_to(PROJECT_ROOT)}")
    print(f"✓ Neue leere runs.jsonl angelegt.")


if __name__ == "__main__":
    main()
