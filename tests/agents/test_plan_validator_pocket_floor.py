"""tests/agents/test_plan_validator_pocket_floor.py

Regression: plan_validator's Check 6 ("subtract feature depth > parent depth")
fires false positives on holes that intentionally pierce the pocket floor —
those have depth = depth_local + parent_depth, which is correct.

Fix is a deterministic post-filter on the LLM output: drop Check-6 errors
for features whose params.depth_reference_applied == "pocket_floor". If no
blocking errors remain after the filter, the verdict flips back to valid.

Run 70d27d2f had 3 such false-positive errors and triggered a full retry
cycle (~17s). After the fix, both iterations should pass without retry.
"""

from src.agents.plan_validator import (
    _drop_pocket_floor_depth_errors,
    _has_blocking_errors,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _bp_with_pocket_floor_hole(depth_ref: str = "pocket_floor") -> dict:
    """Blueprint with one hole carrying depth_reference_applied."""
    return {
        "features": {
            "wuerfel": {"id": "wuerfel", "type": "box",
                         "params": {"x": 200, "y": 200, "z": 200},
                         "parent": None, "operation": "add"},
            "tasche_oben_0": {"id": "tasche_oben_0", "type": "pocket_rect",
                                "params": {"x": 60, "y": 40, "depth": 10},
                                "parent": "wuerfel", "operation": "subtract"},
            "hole_in_tasche_oben_0_1": {
                "id": "hole_in_tasche_oben_0_1", "type": "hole_single",
                "params": {"diameter": 10, "depth": 20, "depth_local": 10,
                           "depth_reference_applied": depth_ref},
                "parent": "tasche_oben_0", "operation": "subtract",
            },
        },
    }


def _check6_error(fid: str = "hole_in_tasche_oben_0_1") -> dict:
    return {
        "check": 6, "severity": "ERROR",
        "message": f"Feature '{fid}' (depth 20) is larger than parent 'tasche_oben_0' (depth 10) with operation subtract",
    }


# ── Filter behavior ─────────────────────────────────────────────────────────

class TestPocketFloorFilter:

    def test_drops_check6_for_pocket_floor_hole(self):
        """The exact false positive from Run 70d27d2f gets filtered."""
        bp = _bp_with_pocket_floor_hole("pocket_floor")
        errors = [_check6_error()]
        kept = _drop_pocket_floor_depth_errors(errors, bp)
        assert kept == []

    def test_keeps_check6_for_face_referenced_hole(self):
        """A genuine Check-6 violation (no pocket_floor reference) must pass."""
        bp = _bp_with_pocket_floor_hole("face")
        errors = [_check6_error()]
        kept = _drop_pocket_floor_depth_errors(errors, bp)
        assert kept == errors

    def test_keeps_check6_when_depth_ref_field_missing(self):
        """If the feature has no depth_reference_applied, keep the error."""
        bp = _bp_with_pocket_floor_hole("pocket_floor")
        # Strip the field — simulates an upstream that didn't set it.
        bp["features"]["hole_in_tasche_oben_0_1"]["params"].pop(
            "depth_reference_applied"
        )
        errors = [_check6_error()]
        kept = _drop_pocket_floor_depth_errors(errors, bp)
        assert kept == errors

    def test_keeps_unrelated_checks(self):
        """Errors that aren't depth-vs-parent must always survive."""
        bp = _bp_with_pocket_floor_hole("pocket_floor")
        errors = [
            {"check": 1, "severity": "ERROR",
             "message": "No feature with parent=null"},
            {"check": 2, "severity": "ERROR",
             "message": "Duplicate feature ID 'hole_x'"},
        ]
        kept = _drop_pocket_floor_depth_errors(errors, bp)
        assert kept == errors

    def test_filters_only_matching_feature_id(self):
        """Multiple Check-6 errors: only the pocket_floor one is dropped."""
        bp = _bp_with_pocket_floor_hole("pocket_floor")
        # Add a second hole with face reference that has a real violation
        bp["features"]["hole_through_part"] = {
            "id": "hole_through_part", "type": "hole_single",
            "params": {"diameter": 5, "depth": 999,
                       "depth_reference_applied": "face"},
            "parent": "wuerfel", "operation": "subtract",
        }
        errors = [
            _check6_error("hole_in_tasche_oben_0_1"),
            _check6_error("hole_through_part"),
        ]
        kept = _drop_pocket_floor_depth_errors(errors, bp)
        assert len(kept) == 1
        assert "hole_through_part" in kept[0]["message"]

    def test_handles_missing_feature_gracefully(self):
        """Error references an unknown feature ID — keep the error (we
        cannot prove it is a pocket-floor case)."""
        bp = _bp_with_pocket_floor_hole("pocket_floor")
        errors = [_check6_error("ghost_hole")]
        kept = _drop_pocket_floor_depth_errors(errors, bp)
        assert kept == errors

    def test_handles_double_quotes_in_message(self):
        """Some prompts produce double-quoted feature IDs — must still match."""
        bp = _bp_with_pocket_floor_hole("pocket_floor")
        errors = [{
            "check": 6, "severity": "ERROR",
            "message": 'Feature "hole_in_tasche_oben_0_1" exceeds parent "tasche_oben_0"',
        }]
        kept = _drop_pocket_floor_depth_errors(errors, bp)
        assert kept == []


# ── Verdict flip ────────────────────────────────────────────────────────────

class TestVerdictFlip:

    def test_no_blocking_errors_when_only_warnings(self):
        errors = [{"check": 8, "severity": "WARNING",
                    "message": "Wandstärke knapp"}]
        assert _has_blocking_errors(errors) is False

    def test_blocking_when_error_present(self):
        errors = [{"check": 1, "severity": "ERROR",
                    "message": "Missing parent=null feature"}]
        assert _has_blocking_errors(errors) is True

    def test_empty_list_not_blocking(self):
        assert _has_blocking_errors([]) is False
