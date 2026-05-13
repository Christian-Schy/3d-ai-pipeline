from pathlib import Path

from src.ui.golden_cases import (
    CHOICE_SEPARATOR,
    SOURCE_COMPONENTS,
    discover_golden_cases,
    golden_choices,
    load_golden_case,
    preview_spec,
)


def _write_case(root: Path, slug: str, spec: str, with_expected: bool = True):
    case_dir = root / slug
    case_dir.mkdir(parents=True)
    (case_dir / "spec.txt").write_text(spec, encoding="utf-8")
    if with_expected:
        (case_dir / "expected_blueprint.json").write_text("{}", encoding="utf-8")


def _write_component_specs(root: Path, slug: str, content: str):
    specs_dir = root / "components" / slug / "pipeline"
    specs_dir.mkdir(parents=True)
    (specs_dir / "specs.txt").write_text(content, encoding="utf-8")


def test_discover_golden_cases_only_returns_runnable_pipeline_cases(tmp_path):
    _write_case(tmp_path, "cube", "Ein 30mm Wuerfel")
    _write_case(tmp_path, "missing_expected", "Nicht lauffaehig", with_expected=False)
    _write_case(tmp_path / "components", "component_case", "Nur Component")

    cases = discover_golden_cases(tmp_path)

    assert [case.slug for case in cases] == ["cube"]
    assert cases[0].spec == "Ein 30mm Wuerfel"


def test_discover_component_cases_reads_pipeline_specs_variants(tmp_path):
    _write_component_specs(
        tmp_path,
        "B1",
        "# Kommentar\n\n200mm wuerfel, oben bohrung\n200mm wuerfel, rechts bohrung\n",
    )

    cases = discover_golden_cases(tmp_path, source=SOURCE_COMPONENTS)

    assert [case.key for case in cases] == ["B1 #1", "B1 #2"]
    assert cases[0].spec == "200mm wuerfel, oben bohrung"
    assert cases[1].source == SOURCE_COMPONENTS


def test_golden_choices_include_slug_and_compact_preview(tmp_path):
    _write_case(tmp_path, "cube", "Ein 30mm\nWuerfel mit Bohrung")

    choices = golden_choices(tmp_path)

    assert choices == [f"cube{CHOICE_SEPARATOR}Ein 30mm Wuerfel mit Bohrung"]


def test_load_golden_case_accepts_dropdown_label_or_slug(tmp_path):
    _write_case(tmp_path, "cube", "Ein 30mm Wuerfel")
    label = golden_choices(tmp_path)[0]

    assert load_golden_case(label, tmp_path).slug == "cube"
    assert load_golden_case("cube", tmp_path).spec == "Ein 30mm Wuerfel"
    assert load_golden_case("unknown", tmp_path) is None


def test_load_component_golden_case_accepts_variant_label(tmp_path):
    _write_component_specs(
        tmp_path,
        "B1",
        "200mm wuerfel, oben bohrung\n200mm wuerfel, rechts bohrung\n",
    )
    label = golden_choices(tmp_path, source=SOURCE_COMPONENTS)[1]

    case = load_golden_case(label, tmp_path, source=SOURCE_COMPONENTS)

    assert case.key == "B1 #2"
    assert case.spec == "200mm wuerfel, rechts bohrung"


def test_preview_spec_truncates_long_text():
    preview = preview_spec("x " * 100, max_chars=20)

    assert len(preview) <= 20
    assert preview.endswith("...")
