"""
scripts/save_golden.py — Save a pipeline run as a golden test case.

Usage:
    python -m scripts.save_golden <run_id> --slug NAME [--note "Warum ist das ein Edge-Case?"]
    python -m scripts.save_golden <run_id>          # slug wird auto-generiert aus run_id

Speichert nach tests/golden/<slug>/
    spec.txt                — roher Spec-Text der Pipeline-Eingabe
    expected_blueprint.json — resolved Blueprint (Referenz für Regressionstests)
    notes.md                — Beschreibung + optionale Notiz
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNS_FILE = PROJECT_ROOT / "data" / "sessions" / "runs.jsonl"
GOLDEN_DIR = PROJECT_ROOT / "tests" / "golden"


def find_run(run_id: str) -> dict:
    if not RUNS_FILE.exists():
        sys.exit(f"runs.jsonl nicht gefunden: {RUNS_FILE}")
    with RUNS_FILE.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("run_id", "").startswith(run_id):
                return r
    sys.exit(f"Run '{run_id}' nicht gefunden in {RUNS_FILE}")


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")[:60]


def auto_slug(run: dict, run_id: str) -> str:
    spec = run.get("specification") or run.get("user_input") or ""
    short = slugify(spec)[:40] if spec else ""
    return f"{run_id[:8]}_{short}" if short else run_id[:8]


def save(run_id: str, slug: str | None, note: str) -> Path:
    run = find_run(run_id)
    full_id = run["run_id"]
    slug = slug or auto_slug(run, full_id)

    target = GOLDEN_DIR / slug
    if target.exists():
        sys.exit(f"Ordner existiert bereits: {target}\nAnderen --slug wählen oder alten Ordner löschen.")

    target.mkdir(parents=True)

    # ── spec.txt ──
    spec = run.get("specification") or run.get("user_input") or ""
    (target / "spec.txt").write_text(spec, encoding="utf-8")

    # ── expected_blueprint.json ──
    bp = run.get("blueprint")
    if not bp:
        sys.exit(f"Run {full_id} hat kein Blueprint — wurde die Pipeline vollständig durchgelaufen?")
    (target / "expected_blueprint.json").write_text(
        json.dumps(bp, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # ── notes.md ──
    spec_preview = spec[:120].replace("\n", " ")
    notes = f"""# Golden Case: {slug}

**Run-ID:** {full_id}
**Gespeichert am:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
**Spec:** {spec_preview}

## Was wird hier getestet?

{note or '(keine Notiz — bitte ergänzen was der Edge-Case ist)'}

## Wichtige Felder

<!-- Ergänze welche placement.face / alignment / offset Werte kritisch sind -->
"""
    (target / "notes.md").write_text(notes, encoding="utf-8")

    return target


def main():
    parser = argparse.ArgumentParser(description="Speichere einen Run als Golden Test Case")
    parser.add_argument("run_id", help="run_id (Prefix reicht, z.B. 'abc12345')")
    parser.add_argument("--slug", "-s", default=None, help="Ordnername (nur a-z, 0-9, _)")
    parser.add_argument("--note", "-n", default="", help="Kurze Beschreibung des Edge-Cases")
    args = parser.parse_args()

    path = save(args.run_id, args.slug, args.note)
    print(f"✓ Golden Case gespeichert: {path.relative_to(PROJECT_ROOT)}")
    print(f"  Bitte notes.md ergänzen: was macht diesen Fall besonders?")


if __name__ == "__main__":
    main()
