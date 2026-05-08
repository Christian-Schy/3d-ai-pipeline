"""Component-Goldens fuer aktions_splitter.

Discovery: jeder Ordner `tests/golden/components/<scope>/splitter/` mit
`spec.txt` + `expected_phrases.json` wird ein Test. Optional `teile.json`
(default: [{"id": "wuerfel"}]).

Vergleicht das Splitter-Output (phrase, teil_id, phrase_idx,
parent_phrase_idx) gegen die Erwartung. Phrasen werden auf exakte
String-Gleichheit verglichen (Splitter ist deterministisch, keine
Toleranz noetig).

Siehe `tests/golden/components/README.md` fuer Pattern + Struktur.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.tools.aktions_splitter import split_spec_into_aktionen

COMPONENTS_DIR = Path(__file__).resolve().parent

_DEFAULT_TEILE: list[dict] = [{"id": "wuerfel"}]


def _discover_splitter_cases() -> list[tuple[str, Path]]:
    cases: list[tuple[str, Path]] = []
    if not COMPONENTS_DIR.exists():
        return cases
    for scope_dir in sorted(COMPONENTS_DIR.iterdir()):
        if not scope_dir.is_dir():
            continue
        splitter_dir = scope_dir / "splitter"
        if not splitter_dir.is_dir():
            continue
        if (splitter_dir / "spec.txt").exists() and \
           (splitter_dir / "expected_phrases.json").exists():
            cases.append((scope_dir.name, splitter_dir))
    return cases


_SPLITTER_CASES = _discover_splitter_cases()


def _compare_phrases(got: list[dict], expected: list[dict]) -> list[str]:
    errors: list[str] = []
    if len(got) != len(expected):
        errors.append(
            f"phrase count: erwartet {len(expected)}, bekommen {len(got)}"
        )
        # Show first divergence in detail to make the failure debuggable
        for i in range(min(len(got), len(expected))):
            if got[i].get("phrase") != expected[i].get("phrase"):
                errors.append(
                    f"first divergence at index {i}:\n"
                    f"    erwartet phrase: {expected[i].get('phrase')!r}\n"
                    f"    bekommen phrase: {got[i].get('phrase')!r}"
                )
                break
        return errors

    for i, (g, e) in enumerate(zip(got, expected)):
        for key in ("phrase", "teil_id", "phrase_idx", "parent_phrase_idx"):
            # parent_phrase_idx is allowed to be explicitly None — compare
            # only when key is present in expected.
            if key not in e:
                continue
            gv = g.get(key)
            ev = e.get(key)
            if gv != ev:
                errors.append(
                    f"phrase[{i}].{key}: erwartet {ev!r}, bekommen {gv!r}"
                )
    return errors


@pytest.mark.parametrize(
    "scope,case_dir",
    _SPLITTER_CASES,
    ids=[c[0] for c in _SPLITTER_CASES] or ["no_cases"],
)
def test_splitter_component(scope: str, case_dir: Path) -> None:
    if not _SPLITTER_CASES:
        pytest.skip("Noch keine Splitter-Component-Goldens vorhanden.")
    spec = (case_dir / "spec.txt").read_text(encoding="utf-8").strip()
    expected_doc: Any = json.loads(
        (case_dir / "expected_phrases.json").read_text(encoding="utf-8")
    )
    expected = expected_doc.get("phrases") if isinstance(expected_doc, dict) \
        else expected_doc

    teile_path = case_dir / "teile.json"
    if teile_path.exists():
        teile = json.loads(teile_path.read_text(encoding="utf-8"))
    else:
        teile = _DEFAULT_TEILE

    got = split_spec_into_aktionen(spec, teile)

    errors = _compare_phrases(got, expected)
    if errors:
        pytest.fail(
            f"\nSplitter-Component-Golden '{scope}/splitter' hat "
            f"{len(errors)} Abweichung(en):\n"
            + "\n".join(f"  ✗ {e}" for e in errors)
        )
