"""
tests/test_config.py — Tests fuer den Config-Loader.

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

    def test_partial_yaml_fills_missing_with_defaults(self, tmp_path):
        """Fehlende Sections → Default-Objekte."""
        cfg = self.load("models:\n  coder: 'custom-coder'\n", tmp_path)
        assert cfg.models.coder == "custom-coder"
        assert cfg.sandbox.timeout_seconds == 60

    def test_aktions_klassifizierer_model_is_validated(self, tmp_path):
        """Config must not silently drop the per-action classifier model."""
        cfg = self.load(
            "models:\n  aktions_klassifizierer: 'custom-classifier'\n",
            tmp_path,
        )
        assert cfg.models.aktions_klassifizierer == "custom-classifier"


class TestGetConfig:
    """get_config() Smoke-Test — nur pruefen ob es laeuft."""

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
        assert cfg1 is cfg2  # lru_cache gibt dasselbe Objekt zurueck
