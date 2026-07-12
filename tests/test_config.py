"""Config precedence, profiles, and credential resolution (spec §7)."""

from __future__ import annotations

from pathlib import Path

import pytest

from odoo_sh_cli.config import ConfigManager, CredentialStore
from odoo_sh_cli.errors import ConfigError

CONFIG_TOML = """
default_project = "file-default"

[profiles.default]
project = "file-project"
headless = true
timeout = 45

[profiles.staging]
project = "staging-project"
headless = false
"""


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(CONFIG_TOML)
    return path


def test_flag_beats_env_beats_file(config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ODOO_SH_PROJECT", "env-project")
    mgr = ConfigManager(config_file)

    # Flag wins over env and file.
    assert mgr.resolve(project="flag-project").project == "flag-project"
    # Env wins over file when no flag.
    assert mgr.resolve().project == "env-project"


def test_file_profile_used_when_no_flag_or_env(config_file: Path) -> None:
    mgr = ConfigManager(config_file)
    assert mgr.resolve(profile="default").project == "file-project"
    assert mgr.resolve(profile="staging").project == "staging-project"
    assert mgr.resolve(profile="staging").headless is False


def test_default_project_fallback(config_file: Path) -> None:
    mgr = ConfigManager(config_file)
    # Unknown profile -> falls back to top-level default_project.
    assert mgr.resolve(profile="does-not-exist").project == "file-default"


def test_timeout_default_and_override(config_file: Path) -> None:
    mgr = ConfigManager(config_file)
    assert mgr.resolve(profile="default").timeout == 45
    assert mgr.resolve(profile="default", timeout=99).timeout == 99
    assert mgr.resolve(profile="staging").timeout == 60  # built-in default


def test_headless_env_parsing(config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ODOO_SH_HEADLESS", "0")
    mgr = ConfigManager(config_file)
    assert mgr.resolve(profile="staging").headless is False


def test_require_project_raises_when_missing(tmp_path: Path) -> None:
    mgr = ConfigManager(tmp_path / "missing.toml")
    settings = mgr.resolve()
    with pytest.raises(ConfigError):
        settings.require_project()


def test_credentials_env_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ODOO_SH_GITHUB_USERNAME", "envuser")
    monkeypatch.setenv("ODOO_SH_GITHUB_PASSWORD", "envpass")
    store = CredentialStore()
    store.set("github_username", "keyuser")  # keyring value should lose to env
    creds = store.load()
    assert creds.username == "envuser"
    assert creds.password == "envpass"
    assert creds.totp_secret is None


def test_credentials_from_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    store = CredentialStore()
    store.set("github_username", "keyuser")
    store.set("github_password", "keypass")
    store.set("github_totp_secret", "SECRET32")
    creds = store.load()
    assert creds.username == "keyuser"
    assert creds.totp_secret == "SECRET32"


def test_credentials_missing_raises() -> None:
    with pytest.raises(ConfigError):
        CredentialStore().load()
