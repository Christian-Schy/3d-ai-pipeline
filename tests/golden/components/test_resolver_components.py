"""Component-Goldens fuer den blueprint_resolver.

Discovery: jeder Ordner `tests/golden/components/<scope>/resolver/`
mit `input_semantic.json` + `expected_resolved.json` wird ein Test.
Vergleich mit Toleranzen wie bei den Pipeline-Goldens.

Ziel: schnelle Regressions-Detection fuer die deterministische
Resolver-Mathe (semantic → resolved Blueprint). Kein LLM noetig.

Siehe `tests/golden/components/README.md` fuer Pattern + Struktur.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

from src.tools.blueprint_resolver import resolve_blueprint

COMPONENTS_DIR = Path(__file__).resolve().parent

OFFSET_TOL = 0.1
PARAM_TOL = 0.01
ANGLE_TOL = 0.01


def _approx(a: Any, b: Any, tol: float) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        return math.isclose(float(a), float(b), abs_tol=tol, rel_tol=0)
    except (TypeError, ValueError):
        return str(a) == str(b)


def _compare_placement(got: dict | None, exp: dict | None,
                        path: str, errors: list[str]) -> None:
    if exp is None:
        return
    if got is None:
        errors.append(f"{path}: erwartet placement, bekommen None")
        return
    for field in ("face", "alignment"):
        if exp.get(field) is not None and got.get(field) != exp.get(field):
            errors.append(
                f"{path}.{field}: erwartet {exp[field]!r}, bekommen {got.get(field)!r}"
            )
    for field, tol in [("offset_x", OFFSET_TOL),
                        ("offset_y", OFFSET_TOL),
                        ("angle_deg", ANGLE_TOL)]:
        if exp.get(field) is not None:
            if not _approx(got.get(field), exp[field], tol):
                errors.append(
                    f"{path}.{field}: erwartet {exp[field]}, bekommen "
                    f"{got.get(field)} (±{tol})"
                )


def _compare_params(got: dict, exp: dict, path: str, errors: list[str]) -> None:
    for k, v in exp.items():
        gv = got.get(k)
        if isinstance(v, (int, float)):
            if not _approx(gv, v, PARAM_TOL):
                errors.append(f"{path}.{k}: erwartet {v}, bekommen {gv}")
        elif gv != v:
            errors.append(f"{path}.{k}: erwartet {v!r}, bekommen {gv!r}")


def _compare_resolved(got: dict, expected: dict) -> list[str]:
    errors: list[str] = []
    got_feats = got.get("features") or {}
    exp_feats = expected.get("features") or {}

    for fid in exp_feats.keys() - got_feats.keys():
        errors.append(f"missing feature: {fid}")
    for fid in got_feats.keys() - exp_feats.keys():
        errors.append(f"unexpected feature: {fid}")

    for fid in exp_feats.keys() & got_feats.keys():
        gf = got_feats[fid]
        ef = exp_feats[fid]
        if ef.get("type") and gf.get("type") != ef.get("type"):
            errors.append(
                f"{fid}.type: erwartet {ef['type']!r}, bekommen {gf.get('type')!r}"
            )
        if ef.get("parent") is not None and gf.get("parent") != ef.get("parent"):
            errors.append(
                f"{fid}.parent: erwartet {ef['parent']!r}, bekommen {gf.get('parent')!r}"
            )
        _compare_params(gf.get("params") or {}, ef.get("params") or {},
                         f"{fid}.params", errors)
        _compare_placement(gf.get("placement"), ef.get("placement"),
                            f"{fid}.placement", errors)
    return errors


def _discover_resolver_cases() -> list[tuple[str, Path]]:
    cases = []
    if not COMPONENTS_DIR.exists():
        return cases
    for scope_dir in sorted(COMPONENTS_DIR.iterdir()):
        if not scope_dir.is_dir():
            continue
        resolver_dir = scope_dir / "resolver"
        if not resolver_dir.is_dir():
            continue
        if (resolver_dir / "input_semantic.json").exists() and \
           (resolver_dir / "expected_resolved.json").exists():
            cases.append((scope_dir.name, resolver_dir))
    return cases


_RESOLVER_CASES = _discover_resolver_cases()


@pytest.mark.parametrize(
    "scope,case_dir",
    _RESOLVER_CASES,
    ids=[c[0] for c in _RESOLVER_CASES] or ["no_cases"],
)
def test_resolver_component(scope: str, case_dir: Path) -> None:
    if not _RESOLVER_CASES:
        pytest.skip("Noch keine Resolver-Component-Goldens vorhanden.")
    semantic = json.loads(
        (case_dir / "input_semantic.json").read_text(encoding="utf-8")
    )
    expected = json.loads(
        (case_dir / "expected_resolved.json").read_text(encoding="utf-8")
    )

    resolved = resolve_blueprint(semantic)

    errors = _compare_resolved(resolved, expected)
    if errors:
        pytest.fail(
            f"\nComponent-Golden '{scope}/resolver' hat {len(errors)} "
            f"Abweichung(en):\n" + "\n".join(f"  ✗ {e}" for e in errors)
        )
