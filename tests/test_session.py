"""Encrypted session store: roundtrip, permissions, corruption handling."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from odoo_sh_cli.errors import AuthenticationError
from odoo_sh_cli.session import SessionStore

STATE = {"cookies": [{"name": "session", "value": "secret-cookie"}], "origins": []}


def test_save_load_roundtrip(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "session.enc")
    store.save(STATE)
    assert store.exists()
    assert store.load() == STATE


def test_saved_file_is_encrypted_not_plaintext(tmp_path: Path) -> None:
    path = tmp_path / "session.enc"
    SessionStore(path).save(STATE)
    raw = path.read_bytes()
    assert b"secret-cookie" not in raw


def test_saved_file_permissions_are_0600(tmp_path: Path) -> None:
    path = tmp_path / "session.enc"
    SessionStore(path).save(STATE)
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600


def test_load_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(AuthenticationError):
        SessionStore(tmp_path / "nope.enc").load()


def test_load_corrupt_raises_auth_error(tmp_path: Path) -> None:
    path = tmp_path / "session.enc"
    path.write_bytes(b"not-a-valid-fernet-token")
    with pytest.raises(AuthenticationError):
        SessionStore(path).load()


def test_clear(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "session.enc")
    store.save(STATE)
    assert store.clear() is True
    assert store.clear() is False
