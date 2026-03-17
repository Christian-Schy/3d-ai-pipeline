"""
tests/test_config.py — Tests für den Config-Loader.

Strategie: _load_config(path) direkt testen statt get_config() mit
lru_cache zu patchen. Das vermeidet Fixture-Reihenfolge-Probleme.
"""

import pytest
from pathlib import Path


class TestLoadConfig:
    """_load_config(path) direkt testen — kein Cache, keine Patches."""

    def load(self, yaml_text: str, tmp_path: Path) -> object:
        from src.config.loader import _load_config
        f = tmp_path / "config.yaml"
        f.write_text(yaml_text)
        return _load_config(f)

    def test_defaults_without_yaml(self, tmp_path):
        """Wenn config.yaml fehlt → alle Defaults."""
        from src.config.loader import _load_config, ModelsConfig
        cfg = _load_config(tmp_path / "nonexistent.yaml")
        assert cfg.models.planner == ModelsConfig().planner
        assert cfg.error_loop.max_attempts == 6
        assert cfg.sandbox.timeout_seconds == 60

    def test_yaml_overrides_defaults(self, tmp_path):
        """Werte aus YAML überschreiben Defaults."""
        cfg = self.load("""
models:
  planner: "my-custom-model:7b"
  coder: "qwen3-coder:30b"
error_loop:
  max_attempts: 3
""", tmp_path)
        assert cfg.models.planner == "my-custom-model:7b"
        assert cfg.models.coder == "qwen3-coder:30b"
        assert cfg.error_loop.max_attempts == 3
        # Nicht gesetzte Werte bleiben Default
        from src.config.loader import ModelsConfig
        assert cfg.models.interpreter == ModelsConfig().interpreter

    def test_partial_yaml_fills_missing_with_defaults(self, tmp_path):
        """Fehlende Sections → Default-Objekte."""
        cfg = self.load("models:\n  coder: 'custom-coder'\n", tmp_path)
        assert cfg.models.coder == "custom-coder"
        assert cfg.sandbox.timeout_seconds == 60

    def test_all_model_keys_present(self, tmp_path):
        """Alle erwarteten Agent-Keys sind vorhanden."""
        from src.config.loader import _load_config
        cfg = _load_config(tmp_path / "nonexistent.yaml")
        for key in ["interpreter", "planner", "planner_patch", "planner_revise",
                    "coder", "validator", "code_fixer", "visioner", "modification_interpreter"]:
            assert hasattr(cfg.models, key), f"Missing model key: {key}"

    def test_planner_patch_default_is_smaller_model(self, tmp_path):
        """planner_patch default is smaller than planner — avoids VRAM swap after modification_interpreter."""
        from src.config.loader import _load_config, ModelsConfig
        cfg = _load_config(tmp_path / "nonexistent.yaml")
        assert cfg.models.planner_patch == ModelsConfig().planner_patch
        # patch model should differ from the full planner model
        assert cfg.models.planner_patch != cfg.models.planner

    def test_planner_patch_can_be_overridden(self, tmp_path):
        cfg = self.load("models:\n  planner_patch: 'custom-patch-model'\n", tmp_path)
        assert cfg.models.planner_patch == "custom-patch-model"

    def test_empty_yaml_uses_defaults(self, tmp_path):
        """Leere YAML-Datei → alle Defaults."""
        from src.config.loader import ModelsConfig
        cfg = self.load("", tmp_path)
        assert cfg.models.planner == ModelsConfig().planner

    def test_unknown_fields_ignored(self, tmp_path):
        """Unbekannte Felder in YAML werfen keinen Fehler."""
        cfg = self.load("""
models:
  planner: "test-model"
  unknown_future_agent: "some-model"
""", tmp_path)
        assert cfg.models.planner == "test-model"


class TestGetConfig:
    """get_config() Smoke-Test — nur prüfen ob es läuft."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        from src.config.loader import get_config
        get_config.cache_clear()
        yield
        get_config.cache_clear()

    def test_returns_app_config(self):
        from src.config.loader import get_config, AppConfig
        cfg = get_config()
        assert isinstance(cfg, AppConfig)

    def test_cached_second_call_identical(self):
        from src.config.loader import get_config
        cfg1 = get_config()
        cfg2 = get_config()
        assert cfg1 is cfg2  # lru_cache gibt dasselbe Objekt zurück
