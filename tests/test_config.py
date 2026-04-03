"""
Unit tests for config.py.
"""

import json

import pytest

import config as cfg
from config import DEFAULT_CONFIG, SUPPORTED_BROWSERS, get_browser, load_config

# ── load_config ───────────────────────────────────────────────────────────────


class TestLoadConfig:
    def test_returns_default_when_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "nonexistent.json")
        result = load_config()
        assert result == DEFAULT_CONFIG

    def test_reads_valid_config_file(self, tmp_path, monkeypatch):
        f = tmp_path / "config.json"
        f.write_text(json.dumps({"browser": "firefox"}))
        monkeypatch.setattr(cfg, "CONFIG_FILE", f)
        result = load_config()
        assert result["browser"] == "firefox"

    def test_returns_default_on_bad_json(self, tmp_path, monkeypatch):
        f = tmp_path / "config.json"
        f.write_text("this is not { valid json")
        monkeypatch.setattr(cfg, "CONFIG_FILE", f)
        result = load_config()
        assert result == DEFAULT_CONFIG

    def test_returns_default_when_root_is_not_dict(self, tmp_path, monkeypatch):
        f = tmp_path / "config.json"
        f.write_text("[1, 2, 3]")
        monkeypatch.setattr(cfg, "CONFIG_FILE", f)
        result = load_config()
        assert result == DEFAULT_CONFIG

    def test_extra_keys_preserved(self, tmp_path, monkeypatch):
        f = tmp_path / "config.json"
        f.write_text(json.dumps({"browser": "chrome", "future_key": "value"}))
        monkeypatch.setattr(cfg, "CONFIG_FILE", f)
        result = load_config()
        assert result.get("future_key") == "value"

    def test_returns_fresh_copy_of_default(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "nonexistent.json")
        a = load_config()
        b = load_config()
        a["browser"] = "mutated"
        assert b["browser"] != "mutated"


# ── get_browser ───────────────────────────────────────────────────────────────


class TestGetBrowser:
    def test_default_is_chrome(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "nonexistent.json")
        assert get_browser() == "chrome"

    def test_reads_configured_browser(self, tmp_path, monkeypatch):
        f = tmp_path / "config.json"
        f.write_text(json.dumps({"browser": "firefox"}))
        monkeypatch.setattr(cfg, "CONFIG_FILE", f)
        assert get_browser() == "firefox"

    def test_unknown_browser_falls_back_to_chrome(self, tmp_path, monkeypatch):
        f = tmp_path / "config.json"
        f.write_text(json.dumps({"browser": "lynx"}))
        monkeypatch.setattr(cfg, "CONFIG_FILE", f)
        assert get_browser() == "chrome"

    def test_browser_value_normalised_to_lowercase(self, tmp_path, monkeypatch):
        f = tmp_path / "config.json"
        f.write_text(json.dumps({"browser": "Firefox"}))
        monkeypatch.setattr(cfg, "CONFIG_FILE", f)
        assert get_browser() == "firefox"

    def test_non_string_browser_value_falls_back(self, tmp_path, monkeypatch):
        f = tmp_path / "config.json"
        f.write_text(json.dumps({"browser": 42}))
        monkeypatch.setattr(cfg, "CONFIG_FILE", f)
        assert get_browser() == "chrome"

    @pytest.mark.parametrize("browser", sorted(SUPPORTED_BROWSERS))
    def test_all_supported_browsers_accepted(self, tmp_path, monkeypatch, browser):
        f = tmp_path / "config.json"
        f.write_text(json.dumps({"browser": browser}))
        monkeypatch.setattr(cfg, "CONFIG_FILE", f)
        assert get_browser() == browser


# ── supported_browsers ────────────────────────────────────────────────────────


class TestSupportedBrowsers:
    def test_contains_expected_browsers(self):
        assert "chrome" in SUPPORTED_BROWSERS
        assert "firefox" in SUPPORTED_BROWSERS
        assert "safari" in SUPPORTED_BROWSERS
        assert "brave" in SUPPORTED_BROWSERS
        assert "edge" in SUPPORTED_BROWSERS

    def test_is_frozenset(self):
        assert isinstance(SUPPORTED_BROWSERS, frozenset)


# ── save_config ───────────────────────────────────────────────────────────────


class TestSaveConfig:
    def test_creates_file_and_directory(self, tmp_path, monkeypatch):
        config_dir = tmp_path / "claude-ticker"
        config_file = config_dir / "config.json"
        monkeypatch.setattr(cfg, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(cfg, "CONFIG_FILE", config_file)

        cfg.save_config({"browser": "brave"})

        assert config_file.exists()
        saved = json.loads(config_file.read_text())
        assert saved["browser"] == "brave"

    def test_merges_with_existing_config(self, tmp_path, monkeypatch):
        config_dir = tmp_path / "claude-ticker"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps({"browser": "chrome", "other": "kept"}))
        monkeypatch.setattr(cfg, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(cfg, "CONFIG_FILE", config_file)

        cfg.save_config({"browser": "edge"})

        saved = json.loads(config_file.read_text())
        assert saved["browser"] == "edge"
        assert saved["other"] == "kept"
