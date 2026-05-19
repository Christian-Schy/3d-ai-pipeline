"""Discovery helpers for golden cases shown in the UI."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOLDEN_DIR = PROJECT_ROOT / "tests" / "golden"
CHOICE_SEPARATOR = " :: "
SOURCE_PIPELINE = "pipeline"
SOURCE_COMPONENTS = "components"


@dataclass(frozen=True)
class GoldenCase:
    """A runnable golden case."""

    slug: str
    spec: str
    case_dir: Path
    source: str = SOURCE_PIPELINE
    variant_index: int | None = None

    @property
    def key(self) -> str:
        if self.variant_index is None:
            return self.slug
        return f"{self.slug} #{self.variant_index}"

    @property
    def label(self) -> str:
        preview = preview_spec(self.spec)
        if not preview:
            return self.key
        return f"{self.key}{CHOICE_SEPARATOR}{preview}"


def preview_spec(spec: str, max_chars: int = 96) -> str:
    """Return a compact one-line preview for dropdown labels."""
    text = re.sub(r"\s+", " ", spec).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _read_spec_variants(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _discover_pipeline_golden_cases(golden_dir: Path) -> list[GoldenCase]:
    """Find top-level pipeline goldens with spec.txt and expected_blueprint.json."""
    if not golden_dir.exists():
        return []

    cases: list[GoldenCase] = []
    for case_dir in sorted(golden_dir.iterdir()):
        if not case_dir.is_dir() or case_dir.name == "components":
            continue

        spec_file = case_dir / "spec.txt"
        expected_file = case_dir / "expected_blueprint.json"
        if not spec_file.exists() or not expected_file.exists():
            continue

        spec = spec_file.read_text(encoding="utf-8").strip()
        if not spec:
            continue

        cases.append(
            GoldenCase(
                slug=case_dir.name,
                spec=spec,
                case_dir=case_dir,
                source=SOURCE_PIPELINE,
            )
        )
    return cases


def _discover_component_golden_cases(golden_dir: Path) -> list[GoldenCase]:
    """Find component goldens that expose runnable pipeline specs."""
    components_dir = golden_dir / "components"
    if not components_dir.exists():
        return []

    cases: list[GoldenCase] = []
    for case_dir in sorted(components_dir.iterdir()):
        if not case_dir.is_dir():
            continue

        specs_file = case_dir / "pipeline" / "specs.txt"
        if not specs_file.exists():
            continue

        specs = _read_spec_variants(specs_file)
        for index, spec in enumerate(specs, start=1):
            variant_index = index if len(specs) > 1 else None
            cases.append(
                GoldenCase(
                    slug=case_dir.name,
                    spec=spec,
                    case_dir=case_dir,
                    source=SOURCE_COMPONENTS,
                    variant_index=variant_index,
                )
            )
    return cases


def discover_golden_cases(
    golden_dir: Path = DEFAULT_GOLDEN_DIR,
    source: str = SOURCE_PIPELINE,
) -> list[GoldenCase]:
    """Find runnable golden cases for one UI source."""
    if source == SOURCE_COMPONENTS:
        return _discover_component_golden_cases(golden_dir)
    return _discover_pipeline_golden_cases(golden_dir)


def golden_choices(
    golden_dir: Path = DEFAULT_GOLDEN_DIR,
    source: str = SOURCE_PIPELINE,
) -> list[str]:
    """Return dropdown labels for runnable goldens."""
    return [case.label for case in discover_golden_cases(golden_dir, source=source)]


def load_golden_case(
    choice: str,
    golden_dir: Path = DEFAULT_GOLDEN_DIR,
    source: str = SOURCE_PIPELINE,
) -> GoldenCase | None:
    """Resolve a dropdown label or slug to a golden case."""
    if not choice:
        return None

    key = choice.split(CHOICE_SEPARATOR, 1)[0].strip()
    for case in discover_golden_cases(golden_dir, source=source):
        if case.key == key or case.slug == key:
            return case
    return None
