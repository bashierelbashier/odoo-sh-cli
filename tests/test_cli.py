"""CLI-level behavior: version, auth setup, and error-to-exit-code mapping."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from odoo_sh_cli import __version__, main
from odoo_sh_cli.commands import auth as auth_cmd
from odoo_sh_cli.config import CredentialStore
from odoo_sh_cli.errors import ExitCode, OperationFailedError
from odoo_sh_cli.main import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help_lists_auth_group() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "auth" in result.stdout


def test_auth_setup_stores_credentials() -> None:
    result = runner.invoke(app, ["auth", "setup"], input="botuser\nbotpass\nSECRET32\n")
    assert result.exit_code == 0
    assert "botpass" not in result.stdout  # secret never echoed
    creds = CredentialStore().load()
    assert creds.username == "botuser"
    assert creds.password == "botpass"
    assert creds.totp_secret == "SECRET32"


def test_auth_setup_totp_optional() -> None:
    result = runner.invoke(app, ["auth", "setup"], input="u\np\n\n")
    assert result.exit_code == 0
    assert CredentialStore().load().totp_secret is None


def test_auth_logout_without_session(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeStore:
        def clear(self) -> bool:
            return False

    monkeypatch.setattr(auth_cmd, "SessionStore", FakeStore)
    result = runner.invoke(app, ["auth", "logout"])
    assert result.exit_code == 0
    assert "No session to clear." in result.stdout


def test_run_maps_odoo_error_to_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> None:
        raise OperationFailedError("rebuild refused")

    monkeypatch.setattr(main, "app", boom)
    with pytest.raises(SystemExit) as excinfo:
        main.run()
    assert excinfo.value.code == ExitCode.OPERATION
