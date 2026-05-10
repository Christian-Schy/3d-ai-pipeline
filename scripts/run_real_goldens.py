"""
scripts/run_real_goldens.py — Real-Run-Heatmap fuer Component-Goldens.

Nimmt jede `tests/golden/components/<X>/pipeline/specs.txt` und faehrt sie
durch die echte LLM-Pipeline (`PipelineRunner.run`). Vergleicht das resolved
Blueprint mit `tests/golden/components/<X>/resolver/expected_resolved.json`.

Output:
    - Tabellarisch zeilenweise pro Spec (PASS/FAIL + erste Bug-Layer + erster Fehler)
    - Heatmap-Summary: Fail-Counts pro Pipeline-Layer
    - Persistent als `data/sessions/heatmap_<datum>_<zeit>.md`

Usage:
    .venv/bin/python -m scripts.run_real_goldens
    .venv/bin/python -m scripts.run_real_goldens --filter B
    .venv/bin/python -m scripts.run_real_goldens --filter B1
    .venv/bin/python -m scripts.run_real_goldens --filter NEST,T
    .venv/bin/python -m scripts.run_real_goldens --first-only   # nur 1. Spec pro Component
    .venv/bin/python -m scripts.run_real_goldens --no-persist   # kein heatmap_<datum>.md

Exit-Code: 0 wenn alle PASS, 1 sonst.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMPONENTS_DIR = PROJECT_ROOT / "tests" / "golden" / "components"
HEATMAP_DIR = PROJECT_ROOT / "data" / "sessions"

OFFSET_TOL = 0.1
PARAM_TOL = 0.01
ANGLE_TOL = 0.01

PIPELINE_LAYERS = [
    "punctuation",
    "interpreter",
    "inventar",
    "aktions_splitter",
    "aktions_klassifizierer",
    "text_splitter",
    "position_extractor",
    "feature_definierer",
    "aktions_aggregator",
    "platzierer",
    "pocket_child_placer",
    "blueprint_resolver",
    "coordinate_validator",
    "plan_validator",
]


# --------------------------------------------------------------------------
# Spec discovery
# --------------------------------------------------------------------------

def _read_specs_file(path: Path) -> list[str]:
    """Eine Spec pro Zeile, # Kommentare und Leerzeilen werden ignoriert."""
    specs = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        specs.append(line)
    return specs


def discover_cases(filter_spec: str | None, first_only: bool) -> list[dict]:
    """Discover all (component, spec) pairs in tests/golden/components/<X>/pipeline/specs.txt."""
    cases = []
    if not COMPONENTS_DIR.exists():
        return cases

    filters = [f.strip() for f in (filter_spec or "").split(",") if f.strip()]

    for comp_dir in sorted(COMPONENTS_DIR.iterdir()):
        if not comp_dir.is_dir() or comp_dir.name.startswith("_"):
            continue
        specs_file = comp_dir / "pipeline" / "specs.txt"
        expected_file = comp_dir / "resolver" / "expected_resolved.json"
        if not specs_file.exists() or not expected_file.exists():
            continue

        if filters and not any(comp_dir.name.startswith(f) or f in comp_dir.name for f in filters):
            continue

        specs = _read_specs_file(specs_file)
        if not specs:
            continue
        if first_only:
            specs = specs[:1]

        for i, spec in enumerate(specs):
            cases.append({
                "component": comp_dir.name,
                "variant_idx": i,
                "spec": spec,
                "expected_path": expected_file,
            })
    return cases


# --------------------------------------------------------------------------
# Blueprint compare (gleiche Toleranzen wie test_resolver_components.py)
# --------------------------------------------------------------------------

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


def _feature_sig(feat: dict) -> tuple:
    """Coarse signature for sibling-pairing. parent ist KEIN Teil davon —
    der Parent wird durch die rekursive Walk-Order schon eingegrenzt.
    """
    placement = feat.get("placement") or {}
    return (
        feat.get("type") or "",
        placement.get("face") or "",
    )


def _offset_distance(a: dict, b: dict) -> float:
    pa = a.get("placement") or {}
    pb = b.get("placement") or {}
    try:
        ax = float(pa.get("offset_x") or 0)
        ay = float(pa.get("offset_y") or 0)
        bx = float(pb.get("offset_x") or 0)
        by = float(pb.get("offset_y") or 0)
        return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
    except (TypeError, ValueError):
        return float("inf")


def _angle_distance(a: dict, b: dict) -> float:
    pa = a.get("placement") or {}
    pb = b.get("placement") or {}
    try:
        return abs(float(pa.get("angle_deg") or 0) - float(pb.get("angle_deg") or 0))
    except (TypeError, ValueError):
        return 0.0


def _param_distance(a: dict, b: dict) -> float:
    ap = a.get("params") or {}
    bp = b.get("params") or {}
    distance = 0.0
    for key, aval in ap.items():
        bval = bp.get(key)
        if isinstance(aval, (int, float)) and isinstance(bval, (int, float)):
            distance += abs(float(aval) - float(bval))
        elif bval != aval:
            distance += 100.0
    return distance


def _pair_cost(expected_feat: dict, got_feat: dict) -> float:
    """Cost for pairing siblings with the same coarse signature.

    Offset remains dominant, but angle/params break ties for cases like
    N_kombo where multiple slots share (type, face, offset) and only differ
    by rotation/length.
    """
    return (
        _offset_distance(expected_feat, got_feat)
        + _angle_distance(expected_feat, got_feat) * 0.1
        + _param_distance(expected_feat, got_feat) * 0.01
    )


def _pair_level(
    expected: dict, got: dict,
    exp_parent: str | None, got_parent: str | None,
    pairs: list, unmatched_exp: list, unmatched_got: list,
) -> None:
    """Pair sibling-features at one parent-level by signature, then by offset-distance.

    Recurses into matched pairs to pair grandchildren (NEST: bohrung-in-tasche).
    Mismatches surface as unmatched_* with the offending feature's signature
    so layer-attribution kann face/type-Bugs erkennen.
    """
    from collections import defaultdict

    exp_kids = [(eid, ef) for eid, ef in expected.items() if ef.get("parent") == exp_parent]
    got_kids = [(gid, gf) for gid, gf in got.items() if gf.get("parent") == got_parent]

    exp_by_sig: dict[tuple, list] = defaultdict(list)
    got_by_sig: dict[tuple, list] = defaultdict(list)
    for eid, ef in exp_kids:
        exp_by_sig[_feature_sig(ef)].append((eid, ef))
    for gid, gf in got_kids:
        got_by_sig[_feature_sig(gf)].append((gid, gf))

    for sig in set(exp_by_sig) | set(got_by_sig):
        exp_list = list(exp_by_sig.get(sig, []))
        got_list = list(got_by_sig.get(sig, []))
        # Greedy nearest-neighbor by offset-distance — bei mehreren gleichen
        # Signaturen (z.B. 6 hole_single auf >Z) macht das eine sinnvolle
        # 1:1-Zuordnung, sodass der Compare den naechsten Nachbarn auf Diffs
        # prueft statt willkuerlich nach ID zu matchen.
        while exp_list and got_list:
            best = None
            best_cost = float("inf")
            for ei, (eid, ef) in enumerate(exp_list):
                for gi, (gid, gf) in enumerate(got_list):
                    cost = _pair_cost(ef, gf)
                    if cost < best_cost:
                        best_cost = cost
                        best = (ei, gi, eid, gid, ef, gf)
            if best is None:
                break
            ei, gi, eid, gid, ef, gf = best
            pairs.append((eid, gid, ef, gf))
            exp_list.pop(ei)
            got_list.pop(gi)
            # Rekursion: paare grand-children (NEST)
            _pair_level(expected, got, eid, gid, pairs, unmatched_exp, unmatched_got)

        for eid, ef in exp_list:
            unmatched_exp.append((eid, ef))
        for gid, gf in got_list:
            unmatched_got.append((gid, gf))


def compare_blueprints(got: dict, expected: dict) -> list[str]:
    """Strukturelles Match: paart Features by (parent, type, face), dann nach
    offset-distance. Reports Diffs auf gepaarten Features + unmatched Listen.
    Tolerant gegen unterschiedliche IDs zwischen handgeschriebener
    expected_resolved.json und Pipeline-erzeugten auto-IDs.
    """
    errors: list[str] = []
    got_feats = got.get("features") or {}
    exp_feats = expected.get("features") or {}

    pairs: list = []
    unmatched_exp: list = []
    unmatched_got: list = []
    _pair_level(exp_feats, got_feats, None, None, pairs, unmatched_exp, unmatched_got)

    for eid, ef in unmatched_exp:
        sig = _feature_sig(ef)
        errors.append(
            f"missing: expected[{eid}] type={sig[0]!r} face={sig[1]!r} "
            f"parent={ef.get('parent')!r}"
        )
    for gid, gf in unmatched_got:
        sig = _feature_sig(gf)
        errors.append(
            f"unexpected: got[{gid}] type={sig[0]!r} face={sig[1]!r} "
            f"parent={gf.get('parent')!r}"
        )

    for eid, gid, ef, gf in pairs:
        # Verwende exp_id als kanonisches Label (gleicher Name wie in der
        # expected_resolved.json — leichter zum Korrelieren).
        path = f"{eid}↔{gid}"
        if ef.get("type") and gf.get("type") != ef.get("type"):
            errors.append(
                f"{path}.type: erwartet {ef['type']!r}, bekommen {gf.get('type')!r}"
            )
        _compare_params(
            gf.get("params") or {}, ef.get("params") or {},
            f"{path}.params", errors,
        )
        _compare_placement(
            gf.get("placement"), ef.get("placement"),
            f"{path}.placement", errors,
        )
    return errors


# --------------------------------------------------------------------------
# Layer attribution — heuristisch
# --------------------------------------------------------------------------

def attribute_layer(state: dict, errors: list[str], expected: dict) -> tuple[str, str]:
    """Beste Schaetzung welcher Layer die Pipeline gebrochen hat.

    Returns: (layer_name, kurze Diagnose).

    Heuristik:
    - Pipeline-Crash mit explizitem error_tag → der Trace mit error_tag
    - Kein Blueprint produziert → letzter ausgefuehrter Trace
    - Blueprint da, aber Diff:
      - missing/extra teile (root features) → inventar
      - parent-rewriting falsch (parent != expected) → aktions_aggregator
      - feature-count pro teil falsch → aktions_splitter / feature_definierer
      - feature.type falsch → aktions_klassifizierer
      - placement.face/side falsch → aktions_klassifizierer
      - offset_x/y oder params falsch → blueprint_resolver / platzierer
      - sonst → blueprint_resolver
    """
    traces = state.get("agent_traces") or []
    blueprint = state.get("blueprint") or {}

    # 1. Pipeline-Crash mit Error-Tag
    error_traces = [t for t in traces if t.get("error_tag")]
    if error_traces:
        last = error_traces[-1]
        return (
            last.get("agent", "unknown"),
            f"error_tag={last.get('error_tag')} note={last.get('error_note', '')[:80]}",
        )

    # 2. Kein Blueprint produziert
    if not blueprint or not blueprint.get("features"):
        if state.get("execution_error"):
            return ("executor", str(state["execution_error"])[:80])
        if traces:
            return (traces[-1].get("agent", "unknown"), "no blueprint produced")
        return ("unknown", "no blueprint, no traces")

    # 3. Diff vorhanden — Layer raten anhand der strukturellen Diffs
    exp_feats = expected.get("features") or {}
    got_feats = blueprint.get("features") or {}

    exp_roots_n = sum(1 for f in exp_feats.values() if f.get("parent") is None)
    got_roots_n = sum(1 for f in got_feats.values() if f.get("parent") is None)

    # 3a. Wurzel-Teile-Anzahl falsch → Inventar
    if exp_roots_n != got_roots_n:
        return ("inventar", f"root parts: erwartet {exp_roots_n}, bekommen {got_roots_n}")

    # 3b. Gesamt-Feature-Count falsch → Splitter (Phrasen verloren) oder
    # feature_definierer (None-Drops). Nutze Total weil wir die Per-Root-
    # Korrelation jetzt durch das Pairing schon haben.
    exp_total = len(exp_feats)
    got_total = len(got_feats)
    if exp_total != got_total:
        # 0 features → splitter dropped everything. Sonst eher feature_definierer.
        if got_total <= got_roots_n:  # nur Roots, keine Children
            return (
                "aktions_splitter",
                f"keine Features unter Wurzel-Teilen: erwartet {exp_total}, bekommen {got_total}",
            )
        return (
            "aktions_splitter",
            f"feature-count: erwartet {exp_total}, bekommen {got_total}",
        )

    # 3c. unmatched-Pairs unterschiedlicher Face → Klassifizierer (Side-Bug
    # wie B_kombo_bohrungen_oben mit 1 bohrung auf <Z statt >Z).
    miss_faces: dict[str, int] = {}
    extra_faces: dict[str, int] = {}
    for err in errors:
        if err.startswith("missing:"):
            face = err.split("face=")[-1].split()[0] if "face=" in err else ""
            miss_faces[face] = miss_faces.get(face, 0) + 1
        elif err.startswith("unexpected:"):
            face = err.split("face=")[-1].split()[0] if "face=" in err else ""
            extra_faces[face] = extra_faces.get(face, 0) + 1
    if miss_faces and extra_faces:
        m_face = next(iter(miss_faces.keys()))
        e_face = next(iter(extra_faces.keys()))
        return (
            "aktions_klassifizierer",
            f"face-mismatch: {sum(miss_faces.values())} fehlt auf {m_face}, "
            f"{sum(extra_faces.values())} extra auf {e_face}",
        )

    # 3d. Diffs auf gepaarten Features
    for err in errors:
        if ".type:" in err:
            return ("aktions_klassifizierer", err)
    for err in errors:
        if ".face:" in err or ".side:" in err:
            return ("aktions_klassifizierer", err)
    for err in errors:
        if ".params." in err:
            return ("feature_definierer", err)
    for err in errors:
        if ".offset_x:" in err or ".offset_y:" in err or ".angle_deg:" in err:
            return ("blueprint_resolver", err)
        if ".alignment:" in err:
            return ("platzierer", err)

    return ("blueprint_resolver", errors[0] if errors else "unknown diff")


# --------------------------------------------------------------------------
# Pipeline-Run pro Spec
# --------------------------------------------------------------------------

def run_one(spec: str, expected: dict, persist_to_jsonl: bool = True) -> dict:
    """Run pipeline once. Return dict with status + diagnose + raw state.

    persist_to_jsonl: appends an entry to data/sessions/runs.jsonl with the
    final pipeline state, so the user can deep-dive via run_id even if the
    pipeline ended early (Coder disabled / template-mode crash / etc.).
    """
    from src.graph.pipeline import PipelineRunner
    from src.tools.session_logger import SessionLogger

    started = time.time()
    runner = PipelineRunner()
    state = None
    crash_exc = None

    try:
        state = runner.run(spec, ask_user=lambda q: "")
    except Exception as exc:
        crash_exc = exc

    duration = round(time.time() - started, 1)

    run_id = ""
    if persist_to_jsonl and state is not None:
        try:
            run_id = SessionLogger().log_run(
                state, feedback="", task_id="real_goldens_heatmap"
            )
            state["run_id"] = run_id
        except Exception as log_exc:
            run_id = f"<persist_failed:{type(log_exc).__name__}>"

    if crash_exc is not None:
        return {
            "status": "CRASH",
            "layer": "pipeline",
            "diagnose": f"{type(crash_exc).__name__}: {str(crash_exc)[:100]}",
            "duration_s": duration,
            "errors": [],
            "traceback": traceback.format_exc(),
            "state": state,
            "run_id": run_id,
        }

    blueprint = state.get("blueprint") or {}
    if not blueprint or not blueprint.get("features"):
        layer, diag = attribute_layer(state, [], expected)
        return {
            "status": "FAIL",
            "layer": layer,
            "diagnose": diag,
            "duration_s": duration,
            "errors": [],
            "state": state,
            "run_id": run_id,
        }

    errors = compare_blueprints(blueprint, expected)
    if not errors:
        return {
            "status": "PASS",
            "layer": "—",
            "diagnose": "ok",
            "duration_s": duration,
            "errors": [],
            "state": state,
            "run_id": run_id,
        }

    layer, diag = attribute_layer(state, errors, expected)
    return {
        "status": "FAIL",
        "layer": layer,
        "diagnose": diag,
        "duration_s": duration,
        "errors": errors,
        "state": state,
        "run_id": run_id,
    }


# --------------------------------------------------------------------------
# Replay Mode — persistierte Runs offline neu auswerten
# --------------------------------------------------------------------------

def _load_replay_runs() -> list[dict]:
    """Liefert persistierte Heatmap-Runs (task_id=real_goldens_heatmap) aus runs.jsonl."""
    runs_file = PROJECT_ROOT / "data" / "sessions" / "runs.jsonl"
    if not runs_file.exists():
        return []
    runs = []
    for line in runs_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("task_id") == "real_goldens_heatmap":
            runs.append(entry)
    return runs


def _find_replay_match(replay_runs: list[dict], spec: str) -> dict | None:
    """Letzten persistierten Run mit dieser Spec finden (jsonl ist append-only,
    spaetere Eintraege sind aktueller).
    """
    spec = spec.strip()
    matches = [r for r in replay_runs if (r.get("user_input") or "").strip() == spec]
    return matches[-1] if matches else None


def _replay_one(entry: dict, expected: dict) -> dict:
    """Compare-Pipeline auf einem persistierten Run-Eintrag — kein LLM-Call."""
    blueprint = entry.get("blueprint") or {}
    state = {
        "agent_traces": entry.get("agent_traces", []),
        "blueprint": blueprint,
        "execution_error": entry.get("execution_error", ""),
    }
    rid = entry.get("run_id", "")
    if not blueprint or not blueprint.get("features"):
        layer, diag = attribute_layer(state, [], expected)
        return {
            "status": "FAIL", "layer": layer, "diagnose": diag,
            "duration_s": 0, "errors": [], "state": state, "run_id": rid,
        }
    errors = compare_blueprints(blueprint, expected)
    if not errors:
        return {
            "status": "PASS", "layer": "—", "diagnose": "ok (replay)",
            "duration_s": 0, "errors": [], "state": state, "run_id": rid,
        }
    layer, diag = attribute_layer(state, errors, expected)
    return {
        "status": "FAIL", "layer": layer, "diagnose": diag,
        "duration_s": 0, "errors": errors, "state": state, "run_id": rid,
    }


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def _row(case: dict, result: dict) -> str:
    rid = result.get("run_id") or "????????"
    return (
        f"{result['status']:5}  {case['component']:36} v{case['variant_idx']}  "
        f"{result['duration_s']:>6}s  run={rid:8}  "
        f"layer={result['layer']:24}  {result['diagnose'][:80]}"
    )


def _heatmap_summary(results: list[tuple[dict, dict]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for _case, res in results:
        if res["status"] != "PASS":
            counts[res["layer"]] = counts.get(res["layer"], 0) + 1
    return counts


def write_persistent_report(results: list[tuple[dict, dict]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    total = len(results)
    pass_n = sum(1 for _, r in results if r["status"] == "PASS")
    fail_n = total - pass_n
    heatmap = _heatmap_summary(results)
    lines = [
        f"# Real-Run-Heatmap {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"**Total:** {total}  **PASS:** {pass_n}  **FAIL:** {fail_n}",
        "",
        "## Layer-Heatmap (Fail-Counts)",
        "",
        "| Layer | Fails |",
        "|-------|------:|",
    ]
    for layer in PIPELINE_LAYERS + ["aktions_aggregator", "executor", "pipeline", "unknown"]:
        if layer in heatmap:
            lines.append(f"| {layer} | {heatmap[layer]} |")
    other = {k: v for k, v in heatmap.items() if k not in PIPELINE_LAYERS + ["aktions_aggregator", "executor", "pipeline", "unknown"]}
    for k, v in other.items():
        lines.append(f"| {k} | {v} |")
    lines.extend(["", "## Per-Spec-Ergebnisse", ""])

    for case, res in results:
        lines.append(f"### {res['status']}  {case['component']}  v{case['variant_idx']}")
        lines.append("")
        lines.append(f"- **Spec:** `{case['spec']}`")
        lines.append(f"- **Layer:** `{res['layer']}`")
        lines.append(f"- **Diagnose:** {res['diagnose']}")
        lines.append(f"- **Dauer:** {res['duration_s']}s")
        if res.get("errors"):
            lines.append(f"- **Diffs ({len(res['errors'])}):**")
            for e in res["errors"][:20]:
                lines.append(f"    - `{e}`")
            if len(res["errors"]) > 20:
                lines.append(f"    - … ({len(res['errors']) - 20} weitere)")
        rid = res.get("run_id") or ""
        if rid:
            lines.append(f"- **Run-ID:** `{rid}` (in data/sessions/runs.jsonl)")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Real-Run-Heatmap fuer Component-Goldens")
    parser.add_argument("--filter", "-f", default=None,
                         help="Component-Praefix(e), kommagetrennt: 'B', 'B1', 'NEST,T'")
    parser.add_argument("--first-only", action="store_true",
                         help="Nur die erste Spec-Variante pro Component (schneller Smoke)")
    parser.add_argument("--no-persist", action="store_true",
                         help="Kein heatmap_<datum>.md persistieren")
    parser.add_argument("--no-jsonl", action="store_true",
                         help="Runs nicht in data/sessions/runs.jsonl appenden")
    parser.add_argument("--replay", action="store_true",
                         help="Statt LLM-Pipeline: persistierte runs.jsonl-Eintraege "
                              "(task_id=real_goldens_heatmap) neu gegen die aktuellen "
                              "expected_resolved.json auswerten. Spart ~20 min bei "
                              "Compare-Logik-Aenderungen.")
    parser.add_argument("--list", action="store_true",
                         help="Nur Cases listen, nicht laufen lassen")
    args = parser.parse_args()

    cases = discover_cases(args.filter, args.first_only)
    if not cases:
        filt = f" (filter={args.filter})" if args.filter else ""
        print(f"Keine Component-Goldens mit pipeline/specs.txt gefunden{filt}.")
        return 1

    print(f"\n{len(cases)} Spec(s) zu laufen "
          f"({len({c['component'] for c in cases})} Components)")
    if args.list:
        for case in cases:
            print(f"  {case['component']:36} v{case['variant_idx']}  "
                  f"{case['spec'][:70]}…" if len(case['spec']) > 70 else f"  {case['component']:36} v{case['variant_idx']}  {case['spec']}")
        return 0
    print()

    replay_runs = _load_replay_runs() if args.replay else None
    if args.replay and not replay_runs:
        print("Keine task_id=real_goldens_heatmap Runs in data/sessions/runs.jsonl gefunden.")
        return 1

    results: list[tuple[dict, dict]] = []
    for case in cases:
        # Lazy-load expected each time (Pfade unterscheiden sich pro Case)
        expected = json.loads(case["expected_path"].read_text(encoding="utf-8"))
        if args.replay:
            entry = _find_replay_match(replay_runs, case["spec"])
            if entry is None:
                res = {
                    "status": "SKIP",
                    "layer": "—",
                    "diagnose": "kein replay-run mit dieser spec",
                    "duration_s": 0,
                    "errors": [],
                    "state": None,
                    "run_id": "",
                }
            else:
                res = _replay_one(entry, expected)
        else:
            print(f"  → {case['component']:36} v{case['variant_idx']}  laeuft …", flush=True)
            res = run_one(case["spec"], expected, persist_to_jsonl=not args.no_jsonl)
        results.append((case, res))
        if not args.replay:
            print(f"\033[1A\033[K  {_row(case, res)}", flush=True)
        else:
            print(f"  {_row(case, res)}", flush=True)

    print()
    print("─" * 80)
    pass_n = sum(1 for _, r in results if r["status"] == "PASS")
    fail_n = len(results) - pass_n
    print(f"GESAMT: {pass_n} PASS / {fail_n} FAIL  (von {len(results)} Specs)")
    print()
    print("Layer-Heatmap (Fail-Counts):")
    heatmap = _heatmap_summary(results)
    if not heatmap:
        print("  (keine Fails)")
    else:
        for layer, count in sorted(heatmap.items(), key=lambda kv: (-kv[1], kv[0])):
            bar = "█" * count
            print(f"  {layer:28} {count:3}  {bar}")

    if not args.no_persist:
        path = HEATMAP_DIR / f"heatmap_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        write_persistent_report(results, path)
        print(f"\nReport: {path.relative_to(PROJECT_ROOT)}")

    return 0 if fail_n == 0 else 1


if __name__ == "__main__":
    sys.path.insert(0, str(PROJECT_ROOT))
    sys.exit(main())
