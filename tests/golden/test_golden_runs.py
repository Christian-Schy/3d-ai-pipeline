"""
tests/golden/test_golden_runs.py — Regressions-Tests gegen gespeicherte Golden Cases.

Jeder Unterordner in tests/golden/<slug>/ wird zu einem pytest-Test.
Der Test fährt die Pipeline mit spec.txt und vergleicht das resolved Blueprint
gegen expected_blueprint.json.

Starten:
    pytest -m slow tests/golden/test_golden_runs.py -v
    pytest -m slow tests/golden/test_golden_runs.py -v -k "wuerfel"

Was verglichen wird (Toleranzen):
    - placement.face        exakt (">Z", "<X" etc.)
    - placement.alignment   exakt ("centered", "flush_right" etc.)
    - placement.offset_x/y  ±0.1 mm
    - placement.angle_deg   ±0.01 Grad
    - params (x/y/z/...)    ±0.01 mm
    - feature.type          exakt
    - feature.position.side exakt
    - feature count pro Teil exakt

Was NICHT verglichen wird:
    - notes, description, build_order Reihenfolge, stl_path, run_id
    - timestamp-Felder
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.slow

# ── Pfade ─────────────────────────────────────────────────────────────────────

GOLDEN_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = GOLDEN_DIR.parent.parent

# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

FLOAT_TOL = 0.1          # mm-Toleranz für Offsets
PARAM_TOL = 0.01         # mm-Toleranz für Dimensionsparameter
ANGLE_TOL = 0.01         # Grad-Toleranz


def _approx_equal(a: Any, b: Any, tol: float) -> bool:
    """Float-Vergleich mit Toleranz; None == None."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        return math.isclose(float(a), float(b), abs_tol=tol, rel_tol=0)
    except (TypeError, ValueError):
        return str(a) == str(b)


def _compare_params(got: dict, exp: dict, part_id: str, errors: list[str]):
    for key, exp_val in exp.items():
        got_val = got.get(key)
        if isinstance(exp_val, (int, float)):
            if not _approx_equal(got_val, exp_val, PARAM_TOL):
                errors.append(
                    f"{part_id}.params.{key}: erwartet {exp_val}, bekommen {got_val}"
                )
        elif got_val != exp_val:
            errors.append(
                f"{part_id}.params.{key}: erwartet {exp_val!r}, bekommen {got_val!r}"
            )


def _compare_placement(got: dict | None, exp: dict | None, part_id: str, errors: list[str]):
    if exp is None and got is None:
        return
    if exp is None:
        return  # Root-Teil: kein placement erwartet
    if got is None:
        errors.append(f"{part_id}.placement: erwartet Placement, bekommen None")
        return

    # Exakte Felder
    for field in ("face", "alignment"):
        if exp.get(field) is not None and got.get(field) != exp.get(field):
            errors.append(
                f"{part_id}.placement.{field}: erwartet {exp[field]!r}, bekommen {got.get(field)!r}"
            )

    # Float-Felder
    for field, tol in [("offset_x", FLOAT_TOL), ("offset_y", FLOAT_TOL), ("angle_deg", ANGLE_TOL)]:
        if exp.get(field) is not None:
            if not _approx_equal(got.get(field), exp[field], tol):
                errors.append(
                    f"{part_id}.placement.{field}: erwartet {exp[field]}, bekommen {got.get(field)} (±{tol})"
                )


def _compare_features(got_feats: list, exp_feats: list, part_id: str, errors: list[str]):
    if len(got_feats) != len(exp_feats):
        errors.append(
            f"{part_id}.features: erwartet {len(exp_feats)} Features, bekommen {len(got_feats)}"
        )
    for i, (g, e) in enumerate(zip(got_feats, exp_feats)):
        prefix = f"{part_id}.features[{i}]"
        if g.get("type") != e.get("type"):
            errors.append(f"{prefix}.type: erwartet {e.get('type')!r}, bekommen {g.get('type')!r}")
        # Position
        gpos = g.get("position") or {}
        epos = e.get("position") or {}
        for field in ("side", "alignment"):
            if epos.get(field) is not None and gpos.get(field) != epos.get(field):
                errors.append(
                    f"{prefix}.position.{field}: erwartet {epos[field]!r}, bekommen {gpos.get(field)!r}"
                )
        # Params
        _compare_params(g.get("params") or {}, e.get("params") or {}, prefix, errors)


def compare_blueprints(got: dict, expected: dict) -> list[str]:
    """Vergleicht resolved Blueprints. Gibt Liste der Fehler zurück (leer = OK)."""
    errors: list[str] = []

    got_feats = got.get("features") or {}
    exp_feats = expected.get("features") or {}

    # Teile-Menge prüfen
    got_ids = set(got_feats.keys())
    exp_ids = set(exp_feats.keys())
    missing = exp_ids - got_ids
    extra = got_ids - exp_ids
    if missing:
        errors.append(f"Fehlende Teile: {missing}")
    if extra:
        errors.append(f"Unerwartete Teile: {extra}")

    for part_id in exp_ids & got_ids:
        gp = got_feats[part_id]
        ep = exp_feats[part_id]

        if gp.get("type") != ep.get("type"):
            errors.append(f"{part_id}.type: erwartet {ep['type']!r}, bekommen {gp.get('type')!r}")

        _compare_params(gp.get("params") or {}, ep.get("params") or {}, part_id, errors)
        _compare_placement(gp.get("placement"), ep.get("placement"), part_id, errors)

        # Features innerhalb eines Teils (falls vorhanden)
        gf = gp.get("features") or []
        ef = ep.get("features") or []
        if gf or ef:
            _compare_features(gf, ef, part_id, errors)

    return errors


# ── Test-Discovery ────────────────────────────────────────────────────────────

def _discover_golden_cases() -> list[tuple[str, Path]]:
    """Findet alle Golden-Case-Ordner mit spec.txt + expected_blueprint.json."""
    cases = []
    if not GOLDEN_DIR.exists():
        return cases
    for subdir in sorted(GOLDEN_DIR.iterdir()):
        if not subdir.is_dir():
            continue
        spec_file = subdir / "spec.txt"
        expected_file = subdir / "expected_blueprint.json"
        if spec_file.exists() and expected_file.exists():
            cases.append((subdir.name, subdir))
    return cases


_CASES = _discover_golden_cases()


# ── Pipeline Runner (lazy import so pytest collect still works offline) ────────

def _run_pipeline(spec: str) -> dict:
    """Fährt die echte Pipeline und gibt das resolved Blueprint zurück."""
    from src.graph.pipeline import PipelineRunner
    runner = PipelineRunner()
    result = runner.run(spec)
    bp = result.get("blueprint")
    if not bp:
        raise RuntimeError(
            f"Pipeline hat kein Blueprint produziert.\n"
            f"Error: {result.get('error') or result.get('execution_error') or 'unbekannt'}"
        )
    return bp


# ── Parametrisierte Tests ─────────────────────────────────────────────────────

@pytest.mark.parametrize("slug,case_dir", _CASES, ids=[c[0] for c in _CASES])
def test_golden(slug: str, case_dir: Path):
    """Regressions-Test: Pipeline-Output muss dem gespeicherten Blueprint entsprechen."""
    spec = (case_dir / "spec.txt").read_text(encoding="utf-8").strip()
    expected = json.loads((case_dir / "expected_blueprint.json").read_text(encoding="utf-8"))

    got = _run_pipeline(spec)

    errors = compare_blueprints(got, expected)

    if errors:
        notes_file = case_dir / "notes.md"
        notes_hint = ""
        if notes_file.exists():
            notes_hint = f"\n\nNotes:\n{notes_file.read_text(encoding='utf-8')[:300]}"

        pytest.fail(
            f"\nGolden Case '{slug}' hat {len(errors)} Abweichung(en):\n"
            + "\n".join(f"  ✗ {e}" for e in errors)
            + notes_hint
        )
