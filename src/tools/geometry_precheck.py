"""
src/tools/geometry_precheck.py — Deterministischer Geometry-Validator

Läuft NACH sandbox_success, VOR dem LLM-Validator.
Gibt dem LLM-Validator vorberechnete Fakten statt rohe Zahlen.

Usage:
    from src.tools.geometry_precheck import run_geometry_precheck

    report = run_geometry_precheck(
        blueprint=planner_output,       # dict vom Planner
        specification=interpreter_spec, # str
        volume_actual=24133.88,         # float aus STL-Check
        is_watertight=True,
        bbox_dims=(30.0, 30.0, 30.0)   # (width, depth, height)
    )

    # Für den LLM-Validator:
    validator_context = report.to_validator_context()

    # Oder direkt die Issues prüfen:
    if report.has_critical_issues:
        # Zurück zum Planner ohne LLM-Validator
        feedback = report.format_feedback_for_planner()

    # Schneller Check direkt nach Planner (kein STL nötig):
    issues = quick_check(blueprint, specification)
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any


# ─── Data Classes ────────────────────────────────────────────────

@dataclass
class FeatureCheck:
    feature_type: str
    expected: dict
    found: bool = False
    details: str = ""
    confidence: str = "unknown"  # "confirmed", "likely", "missing", "unclear"


@dataclass
class GeometryReport:
    """Vorberechnete Fakten für den LLM-Validator."""

    bbox: dict
    dimensions: dict
    volume_actual: float
    volume_expected_solid: float
    volume_delta: float
    is_watertight: bool
    feature_checks: list[FeatureCheck] = field(default_factory=list)
    feature_count_issues: list[dict] = field(default_factory=list)
    summary: str = ""
    issues: list[str] = field(default_factory=list)

    @property
    def has_critical_issues(self) -> bool:
        """True wenn deterministische Checks echte Fehler gefunden haben."""
        return bool(self.feature_count_issues) or any(
            fc.confidence == "missing" for fc in self.feature_checks
        )

    def to_validator_context(self) -> str:
        """Formatiert den Report als Kontext für den LLM-Validator."""
        lines = [
            "=== GEOMETRY PRE-CHECK RESULTS (deterministic, trustworthy) ===",
            f"Bounding Box: {self.dimensions['width']:.1f} x "
            f"{self.dimensions['depth']:.1f} x "
            f"{self.dimensions['height']:.1f} mm",
            f"Volume actual:              {self.volume_actual:.1f} mm³",
            f"Volume expected (solid):    {self.volume_expected_solid:.1f} mm³",
            f"Volume removed by features: {self.volume_delta:.1f} mm³",
            f"Watertight: {self.is_watertight}",
            "",
        ]

        if self.feature_count_issues:
            lines.append("--- Feature Count Issues (BEFORE geometry check) ---")
            for issue in self.feature_count_issues:
                lines.append(f"  ⚠ {issue['message']}")
            lines.append("")

        lines.append("--- Feature Checks ---")
        for i, fc in enumerate(self.feature_checks, 1):
            lines.append(f"Feature {i} ({fc.feature_type}): {fc.confidence.upper()}")
            lines.append(f"  Blueprint: {json.dumps(fc.expected, ensure_ascii=False)}")
            lines.append(f"  Analysis:  {fc.details}")

        if self.issues:
            lines.append("")
            lines.append("--- Additional Issues ---")
            for issue in self.issues:
                lines.append(f"  ⚠ {issue}")

        lines.append(f"\nSummary: {self.summary}")
        lines.append("=== END PRE-CHECK ===")
        return "\n".join(lines)

    def format_feedback_for_planner(self) -> str:
        """Kurzes, actionable Feedback für den Planner bei Revision."""
        parts = []
        if self.feature_count_issues:
            for issue in self.feature_count_issues:
                parts.append(issue["message"])
        for fc in self.feature_checks:
            if fc.confidence == "missing":
                parts.append(
                    f"Feature '{fc.feature_type}' appears MISSING from the STL. "
                    f"Expected: {json.dumps(fc.expected, ensure_ascii=False)}"
                )
        for issue in self.issues:
            parts.append(issue)
        return " | ".join(parts) if parts else "No issues found."


# ─── Volume Calculations ─────────────────────────────────────────

def _node_volume(node: dict) -> float:
    """Rekursiv das Volumen eines CSG-Baum-Knotens berechnen."""
    t = node.get("type", "")

    if t == "box":
        return node["x"] * node["y"] * node["z"]
    elif t == "cylinder":
        return math.pi * node["radius"] ** 2 * node["height"]
    elif t == "sphere":
        return (4 / 3) * math.pi * node["radius"] ** 3
    elif t == "union":
        # Vereinfacht — ignoriert Überlappungen
        return _node_volume(node["target"]) + _node_volume(node["tool"])
    elif t == "cut":
        return _node_volume(node["target"]) - _node_volume(node["tool"])
    elif t in ("fillet", "chamfer", "shell"):
        return _node_volume(node.get("child", {}))
    else:
        return 0.0


def _estimate_feature_volume(feature: dict, root_dims: dict) -> float:
    """Schätzt das Volumen eines Features."""
    t = feature.get("type", "")

    if t in ("hole", "cbore_hole", "csk_hole"):
        r = feature["diameter"] / 2
        depth = feature.get("depth")
        if depth is None:
            depth = root_dims.get("height", 0)
        vol = math.pi * r ** 2 * depth
        # Counterbore Zusatzvolumen
        if t == "cbore_hole":
            cb_r = feature.get("cbore_diameter", 0) / 2
            cb_d = feature.get("cbore_depth", 0)
            vol += math.pi * (cb_r ** 2 - r ** 2) * cb_d
        return vol

    elif t == "hole_pattern":
        r = feature["diameter"] / 2
        depth = feature.get("depth")
        n = len(feature.get("positions", []))
        if depth is None:
            depth = root_dims.get("height", 0)
        return n * math.pi * r ** 2 * depth

    elif t == "hole_grid":
        r = feature["diameter"] / 2
        depth = feature.get("depth")
        n = feature.get("x_count", 1) * feature.get("y_count", 1)
        if depth is None:
            depth = root_dims.get("height", 0)
        return n * math.pi * r ** 2 * depth

    elif t == "slot":
        w = feature.get("width", 0)
        length = feature.get("length", 0)
        depth = feature.get("depth")
        if depth is None:
            depth = root_dims.get("height", 0)
        # Slot hat Endradien — approximieren
        rect_vol = (length - w) * w * depth if length > w else 0
        cap_vol = math.pi * (w / 2) ** 2 * depth  # Zwei Halbkreise = ein Kreis
        return rect_vol + cap_vol

    elif t == "polygon":
        if feature.get("subtract", False):
            # Reguläres Polygon: A ≈ π * (d/2)²  (Annäherung)
            d = feature.get("diameter", 0)
            h = feature.get("height", 0)
            return math.pi * (d / 2) ** 2 * h * 0.85  # Grobe Annäherung
        return 0.0

    return 0.0


# ─── Feature Count Check ─────────────────────────────────────────

# Keywords pro Sprache (DE + EN)
_FEATURE_KEYWORDS = {
    "hole": [
        "hole", "bohrung", "bore", "drilling", "bohrloch",
        "counterbore", "countersink", "senkbohrung",
    ],
    "slot": [
        "slot", "groove", "nut", "kanal", "schlitz", "einfräsung",
    ],
    "text": [
        "text", "engrav", "emboss", "schrift", "gravur", "prägung",
    ],
    # Note: fillet/chamfer are intentionally NOT checked here.
    # They appear as root-node modifiers (type: "fillet"/"chamfer") OR as boolean cuts
    # — both are valid. The root-node case is caught by _root_has_type elsewhere.
    "corner_cut": [
        "corner cut", "ecke abschneiden", "ecke schneiden",
        "dreiecks", "triangle",
    ],
}


_NEGATIONS = ["no ", "not ", "without ", "kein ", "keine ", "keiner ", "ohne "]


def _keyword_positive(spec_lower: str, keyword: str) -> bool:
    """True wenn das Keyword im Text vorkommt OHNE direkt vorausgehende Negation.

    "no holes"  → False  (Negation erkannt)
    "a hole"    → True   (keine Negation)
    "no fillet" → False
    """
    idx = 0
    while True:
        pos = spec_lower.find(keyword, idx)
        if pos == -1:
            return False
        # Prüfe ob dem Keyword eine Negation vorangeht (max 15 Zeichen zurück)
        prefix = spec_lower[max(0, pos - 15):pos]
        if not any(prefix.endswith(neg) for neg in _NEGATIONS):
            return True  # Keyword ohne Negation gefunden
        idx = pos + 1


def _root_has_type(node: dict, category: str) -> bool:
    """Checks recursively if the root CSG tree contains a node of the given type."""
    if not node:
        return False
    t = node.get("type", "")
    if category in t or t == category:
        return True
    # Recurse into child nodes (fillet/chamfer wrap a child; cut/union have target+tool)
    for key in ("child", "target", "tool"):
        child = node.get(key)
        if isinstance(child, dict) and _root_has_type(child, category):
            return True
    return False


def check_feature_count(specification: str, blueprint: dict) -> list[dict]:
    """
    Prüft ob der Blueprint alle Features aus der Spec enthält.
    Rein deterministisch / keyword-basiert.
    Ignoriert negierte Erwähnungen ("no holes", "ohne Fillet", etc.)
    """
    spec_lower = specification.lower()
    bp_features_raw = blueprint.get("features", [])
    # Feature Tree: features is a dict {id → entry}; CSG-Tree: list
    if isinstance(bp_features_raw, dict):
        bp_features = list(bp_features_raw.values())
    else:
        bp_features = bp_features_raw
    bp_types = [f.get("type", "") for f in bp_features if isinstance(f, dict)]
    root = blueprint.get("root", {})

    issues = []

    for category, keywords in _FEATURE_KEYWORDS.items():
        if any(_keyword_positive(spec_lower, kw) for kw in keywords):
            # Feature ist in der Spec positiv erwähnt — prüfe ob im Blueprint vorhanden.
            # Fillet/chamfer can appear as the root node (wrapping the base shape)
            # rather than in features[] — that is a valid blueprint structure.
            matching = [
                t for t in bp_types
                if category in t or t in category
                or (category == "hole" and "hole" in t)
                or (category == "slot" and t == "slot")
            ]
            if not matching and not _root_has_type(root, category):
                issues.append({
                    "type": "missing_feature",
                    "category": category,
                    "message": (
                        f"Specification mentions '{category}' but blueprint "
                        f"features list ({bp_types}) does not contain it."
                    ),
                })

    return issues


# ─── Depth Check ─────────────────────────────────────────────────

def check_depth_consistency(specification: str, blueprint: dict) -> list[dict]:
    """
    Prüft ob depth-Angaben aus der Spec korrekt im Blueprint sind.
    Sucht nach "Xmm tief/deep" Mustern.
    """
    issues = []
    spec_lower = specification.lower()

    # Regex: Zahl + "mm" + "tief"/"deep" (mit optionalem Whitespace)
    depth_pattern = re.compile(
        r"(\d+(?:\.\d+)?)\s*mm\s*(?:tief|deep|tiefe|depth)", re.IGNORECASE
    )
    matches = depth_pattern.findall(spec_lower)

    if matches:
        specified_depths = [float(m) for m in matches]

        feats_raw = blueprint.get("features", [])
        if isinstance(feats_raw, dict):
            feats_raw = list(feats_raw.values())
        for feat in feats_raw:
            if not isinstance(feat, dict):
                continue
            # Feature Tree stores params nested; CSG-Tree stores them flat
            feat_flat = feat.get("params", feat)
            if feat.get("type") in ("hole", "slot", "cbore_hole", "csk_hole",
                                    "hole_blind", "pocket_rect"):
                # Feature-in-feature: the resolver may have summed parent.depth
                # into params.depth (so the cut spans pocket+hole). The user-
                # facing depth lives in depth_local in that case — match against
                # it so the spec depth comparison stays meaningful.
                if isinstance(feat_flat, dict):
                    bp_depth = feat_flat.get("depth_local")
                    if bp_depth is None:
                        bp_depth = feat_flat.get("depth")
                else:
                    bp_depth = feat.get("depth")
                if bp_depth is None and specified_depths:
                    issues.append({
                        "type": "depth_mismatch",
                        "feature": feat.get("type"),
                        "message": (
                            f"Spec explicitly states depth={specified_depths} mm "
                            f"but blueprint has depth=null (through). "
                            f"This should be a BLIND feature with the specified depth."
                        ),
                    })

    return issues


# ─── Main Function ───────────────────────────────────────────────

def _feature_tree_to_csg_inputs(blueprint: dict) -> tuple[dict, list[dict]]:
    """Convert a Feature Tree blueprint to (root_node, features_list) for the checker.

    Extracts the base feature as a pseudo-CSG root node and converts
    subtractive features to the legacy feature-list format.
    Returns (root_dict, features_list).
    """
    features_dict: dict = blueprint.get("features", {})
    build_order: list = blueprint.get("build_order", [])

    # Find root feature (parent=null)
    root_feat = None
    root_id = None
    for fid in build_order:
        f = features_dict.get(fid, {})
        if f.get("parent") is None:
            root_feat = f
            root_id = fid
            break

    # Build CSG-compatible root node from base feature params
    root_node: dict = {}
    if root_feat:
        params = root_feat.get("params", {})
        if "x" in params and "y" in params and "z" in params:
            root_node = {"type": "box",
                         "x": float(params["x"]),
                         "y": float(params["y"]),
                         "z": float(params["z"])}
        elif "diameter" in params and "height" in params:
            root_node = {"type": "cylinder",
                         "radius": float(params["diameter"]) / 2,
                         "height": float(params["height"])}

    # Convert subtractive features to legacy format
    features_list: list[dict] = []
    for fid in build_order:
        if fid == root_id:
            continue
        f = features_dict.get(fid, {})
        if not isinstance(f, dict):
            continue
        ftype = f.get("type", "")
        params = f.get("params", {})
        if "hole" in ftype:
            legacy: dict = {"type": "hole",
                            "diameter": float(params.get("diameter", 0)),
                            "depth": params.get("depth")}
            if "circle_diameter" in params:
                legacy["type"] = "hole_grid"
                n = int(params.get("n_holes", params.get("count", 1)))
                legacy["x_count"] = n
                legacy["y_count"] = 1
            features_list.append(legacy)
        elif ftype in ("pocket_rect", "slot", "cutout"):
            features_list.append({"type": "slot",
                                   "width": float(params.get("x", params.get("width", 0))),
                                   "depth": params.get("depth")})
    return root_node, features_list


def run_geometry_precheck(
    blueprint: dict,
    specification: str,
    volume_actual: float,
    is_watertight: bool,
    bbox_dims: tuple[float, float, float],
    tolerance: float = 0.15,
) -> GeometryReport:
    """
    Hauptfunktion — nach sandbox_success aufrufen.

    Args:
        blueprint:     Das Blueprint-JSON vom Planner
        specification: Die Spec vom Interpreter
        volume_actual: Gemessenes STL-Volumen in mm³
        is_watertight: Aus dem STL-Check
        bbox_dims:     (width, depth, height) in mm aus BBox
        tolerance:     Toleranz für Volume-Vergleiche (default 15%)

    Returns:
        GeometryReport mit allen Checks und formatted output
    """
    from src.graph.feature_tree import FeatureTree

    width, depth_dim, height = bbox_dims
    root_dims = {"width": width, "depth": depth_dim, "height": height}

    # Adapt Feature Tree blueprints to legacy CSG-Tree format for the checker
    if FeatureTree.is_feature_tree(blueprint):
        root, features = _feature_tree_to_csg_inputs(blueprint)
    else:
        root = blueprint.get("root", {})
        features = blueprint.get("features", [])

    # 1. Erwartetes Solid-Volumen
    volume_solid = _node_volume(root)
    volume_delta = volume_solid - volume_actual

    # 2. Feature-Count-Check (Spec vs Blueprint)
    count_issues = check_feature_count(specification, blueprint)

    # 3. Depth-Check (explizite Tiefe in Spec vs Blueprint)
    depth_issues = check_depth_consistency(specification, blueprint)
    count_issues.extend(depth_issues)

    # 4. Feature-Präsenz-Check (Volume-basiert)
    # features already set above (adapted for Feature Tree or raw CSG-Tree list)
    feature_checks = _check_features_by_volume(
        volume_actual, volume_solid, features, root_dims, tolerance
    )

    # 5. BBox vs Root prüfen
    issues = []
    if root.get("type") == "box":
        expected = sorted([root.get("x", 0), root.get("y", 0), root.get("z", 0)])
        actual = sorted([width, depth_dim, height])
        for exp, act in zip(expected, actual):
            if abs(exp - act) > 0.5:
                issues.append(
                    f"Dimension mismatch: blueprint root says {exp:.1f}mm "
                    f"but STL measures {act:.1f}mm"
                )

    # Volume-Plausibilität
    if volume_delta < -10:
        issues.append(
            f"Volume LARGER than expected solid "
            f"({volume_actual:.0f} > {volume_solid:.0f} mm³)"
        )

    # Missing features aus Volume
    missing = [fc for fc in feature_checks if fc.confidence == "missing"]
    for fc in missing:
        issues.append(f"Feature '{fc.feature_type}' appears MISSING (no volume removed)")

    # Summary
    total_issues = len(count_issues) + len(issues)
    if total_issues == 0:
        summary = "All checks passed — geometry appears correct."
    else:
        summary = f"{total_issues} issue(s) found."

    return GeometryReport(
        bbox={
            "x": [-width / 2, width / 2],
            "y": [-depth_dim / 2, depth_dim / 2],
            "z": [-height / 2, height / 2],
        },
        dimensions=root_dims,
        volume_actual=volume_actual,
        volume_expected_solid=volume_solid,
        volume_delta=volume_delta,
        is_watertight=is_watertight,
        feature_checks=feature_checks,
        feature_count_issues=count_issues,
        summary=summary,
        issues=issues,
    )


def _check_features_by_volume(
    volume_actual: float,
    volume_solid: float,
    features: list[dict],
    root_dims: dict,
    tolerance: float,
) -> list[FeatureCheck]:
    """Prüft Feature-Präsenz anhand Volume-Delta."""
    checks = []
    total_expected_removal = 0.0

    for feat in features:
        fc = FeatureCheck(feature_type=feat.get("type", "unknown"), expected=feat)
        expected_vol = _estimate_feature_volume(feat, root_dims)
        total_expected_removal += expected_vol
        fc.details = f"Expected removal: ~{expected_vol:.1f} mm³"
        checks.append(fc)

    actual_removal = volume_solid - volume_actual

    if not checks:
        return checks

    if actual_removal < 1.0:
        for fc in checks:
            fc.found = False
            fc.confidence = "missing"
            fc.details += f" | Actual removal: {actual_removal:.1f} mm³ — NONE"
    elif len(checks) == 1:
        ratio = (
            actual_removal / total_expected_removal
            if total_expected_removal > 0
            else 0
        )
        if 1 - tolerance <= ratio <= 1 + tolerance:
            checks[0].found = True
            checks[0].confidence = "confirmed"
            checks[0].details += (
                f" | Actual: {actual_removal:.1f} mm³ — MATCHES (ratio={ratio:.2f})"
            )
        elif ratio > 0.3:
            checks[0].found = True
            checks[0].confidence = "likely"
            checks[0].details += (
                f" | Actual: {actual_removal:.1f} mm³ — partial (ratio={ratio:.2f})"
            )
        else:
            checks[0].found = False
            checks[0].confidence = "missing"
            checks[0].details += (
                f" | Actual: {actual_removal:.1f} mm³ — TOO SMALL (ratio={ratio:.2f})"
            )
    else:
        ratio = (
            actual_removal / total_expected_removal
            if total_expected_removal > 0
            else 0
        )
        confidence = "likely" if ratio >= 0.85 else "unclear" if ratio >= 0.5 else "missing"
        for fc in checks:
            fc.found = confidence != "missing"
            fc.confidence = confidence
            fc.details += (
                f" | Combined ratio: {ratio:.2f}, "
                f"total expected: {total_expected_removal:.1f}, "
                f"actual: {actual_removal:.1f} mm³"
            )

    return checks


# ─── Convenience ─────────────────────────────────────────────────

def quick_check(blueprint: dict, specification: str) -> list[dict]:
    """
    Schneller Check OHNE STL-Daten.
    Kann direkt nach dem Planner laufen (vor dem Coder).
    Prüft nur: Feature-Count + Depth-Konsistenz.

    Returns list of issue dicts, empty if all OK.
    """
    issues = check_feature_count(specification, blueprint)
    issues.extend(check_depth_consistency(specification, blueprint))
    return issues
