"""Shared test fixtures. Installs an in-memory keyring so no OS backend is needed."""

from __future__ import annotations

import keyring
import pytest
from keyring.backend import KeyringBackend

from odoo_sh_cli.logging_setup import SecretScrubber


class InMemoryKeyring(KeyringBackend):
    priority = 1  # type: ignore[assignment]

    def __init__(self) -> None:
        super().__init__()
        self._store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self._store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self._store[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self._store.pop((service, username), None)


@pytest.fixture(autouse=True)
def in_memory_keyring() -> None:
    keyring.set_keyring(InMemoryKeyring())


@pytest.fixture(autouse=True)
def reset_scrubber() -> None:
    """Clear registered secrets so class-level state doesn't leak across tests."""
    SecretScrubber._secrets.clear()


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove ODOO_SH_* env vars so tests are isolated from the host."""
    for var in (
        "ODOO_SH_GITHUB_USERNAME",
        "ODOO_SH_GITHUB_PASSWORD",
        "ODOO_SH_GITHUB_TOTP_SECRET",
        "ODOO_SH_PROJECT",
        "ODOO_SH_CONFIG",
        "ODOO_SH_HEADLESS",
    ):
        monkeypatch.delenv(var, raising=False)
