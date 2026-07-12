"""Configuration: file + env + flag precedence, profiles, and credentials.

Precedence (highest wins, spec §7.3):
    command-line flag > environment variable > config file (profile) > default

Runtime config (project, headless, timeout, …) is resolved by
:class:`ConfigManager` into a :class:`Settings` object. Secrets (GitHub
username/password/TOTP) are resolved separately by :class:`CredentialStore`,
which prefers env vars and falls back to the OS keyring.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from .errors import ConfigError

KEYRING_SERVICE = "odoo-sh-cli"
DEFAULT_CONFIG_PATH = Path.home() / ".config" / "odoo-sh-cli" / "config.toml"

# Env var names (spec §7.2).
ENV_USERNAME = "ODOO_SH_GITHUB_USERNAME"
ENV_PASSWORD = "ODOO_SH_GITHUB_PASSWORD"
ENV_TOTP = "ODOO_SH_GITHUB_TOTP_SECRET"
ENV_PROJECT = "ODOO_SH_PROJECT"
ENV_CONFIG = "ODOO_SH_CONFIG"
ENV_HEADLESS = "ODOO_SH_HEADLESS"


class Settings(BaseModel):
    """Fully-resolved runtime configuration for a single command invocation."""

    project: str | None = None
    profile: str = "default"
    headless: bool = True
    timeout: int = 60  # seconds, per-action browser wait
    persist_session: bool = True

    def require_project(self) -> str:
        if not self.project:
            raise ConfigError(
                "No project specified. Pass --project, set ODOO_SH_PROJECT, "
                "or add 'project' to your config profile."
            )
        return self.project


@dataclass
class Credentials:
    username: str
    password: str
    totp_secret: str | None


class ConfigManager:
    """Loads the config file and resolves settings across all sources."""

    def __init__(self, config_path: Path | None = None) -> None:
        env_path = os.environ.get(ENV_CONFIG)
        self.config_path = config_path or (Path(env_path) if env_path else DEFAULT_CONFIG_PATH)
        self._file_data = self._load_file(self.config_path)

    @staticmethod
    def _load_file(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            with path.open("rb") as fh:
                data: dict[str, Any] = tomllib.load(fh)
                return data
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ConfigError(f"Failed to read config file {path}: {exc}") from exc

    def _profile_data(self, profile: str) -> dict[str, Any]:
        profiles: dict[str, Any] = self._file_data.get("profiles", {})
        data: dict[str, Any] = profiles.get(profile, {})
        return data

    def resolve(
        self,
        *,
        profile: str = "default",
        project: str | None = None,
        headless: bool | None = None,
        timeout: int | None = None,
        persist_session: bool | None = None,
    ) -> Settings:
        """Merge sources into a :class:`Settings`. ``None`` flag args mean 'unset'."""
        file_cfg = self._profile_data(profile)

        resolved_project = _first(
            project,
            os.environ.get(ENV_PROJECT),
            file_cfg.get("project"),
            self._file_data.get("default_project"),
        )
        resolved_headless = _first(
            headless,
            _parse_bool(os.environ.get(ENV_HEADLESS)),
            file_cfg.get("headless"),
            True,
        )
        resolved_timeout = _first(timeout, file_cfg.get("timeout"), 60)
        resolved_persist = _first(persist_session, file_cfg.get("persist_session"), True)

        return Settings(
            project=resolved_project,
            profile=profile,
            headless=bool(resolved_headless),
            timeout=int(resolved_timeout),  # type: ignore[arg-type]
            persist_session=bool(resolved_persist),
        )


class CredentialStore:
    """Resolves GitHub credentials: env vars first, then OS keyring."""

    def __init__(self, service: str = KEYRING_SERVICE) -> None:
        self.service = service

    def _get(self, env_var: str, key: str) -> str | None:
        value = os.environ.get(env_var)
        if value:
            return value
        # Import lazily so unit tests and --help don't require a keyring backend.
        import keyring

        return keyring.get_password(self.service, key)

    def set(self, key: str, value: str) -> None:
        import keyring

        keyring.set_password(self.service, key, value)

    def load(self) -> Credentials:
        username = self._get(ENV_USERNAME, "github_username")
        password = self._get(ENV_PASSWORD, "github_password")
        totp = self._get(ENV_TOTP, "github_totp_secret")
        if not username or not password:
            raise ConfigError(
                "GitHub credentials not found. Run 'odoo-sh auth setup' or set "
                f"{ENV_USERNAME} / {ENV_PASSWORD}."
            )
        return Credentials(username=username, password=password, totp_secret=totp)


T = TypeVar("T")


def _first(*values: T | None) -> T | None:
    """Return the first value that is not ``None``."""
    for value in values:
        if value is not None:
            return value
    return None


def _parse_bool(raw: str | None) -> bool | None:
    if raw is None:
        return None
    return raw.strip().lower() in {"1", "true", "yes", "on"}
