"""Command-layer tests for the feature groups, with the service layer faked.

Each command uses ``authed_service(rt, ServiceCls)`` as a context manager; we
patch that symbol in every command module to yield a single recording fake, so
these tests exercise argument parsing, output, and dry-run/confirm plumbing
without a browser.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from typer.testing import CliRunner

from odoo_sh_cli.commands import backup, branch, domain, logs, project, upgrade
from odoo_sh_cli.main import app

runner = CliRunner()
P = ["--project", "demo"]


class FakeService:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    # branch
    def list_branches(self, project, stage=None):
        self.calls.append(("list_branches", project, stage))
        return [{"name": "main", "stage": "production", "url": "u"}]

    def history(self, project, br, limit=20):
        self.calls.append(("history", project, br, limit))
        return [{"event": "build ok"}]

    def rebuild(self, project, br):
        self.calls.append(("rebuild", project, br))

    def delete(self, project, br):
        self.calls.append(("delete", project, br))

    def read_settings(self, project, br):
        self.calls.append(("read_settings", project, br))
        return {"worker_count": "2"}

    def set_settings(self, project, br, pairs):
        self.calls.append(("set_settings", project, br, pairs))
        return {"worker_count": pairs.get("worker_count", "2")}

    # backup
    def list_backups(self, project, br):
        self.calls.append(("list_backups", project, br))
        return [{"id": "b1"}]

    def create(self, project, br, comment=None):
        self.calls.append(("create", project, br, comment))

    def restore(self, project, br, ref):
        self.calls.append(("restore", project, br, ref))

    # logs
    def show(self, project, br, lines=None):
        self.calls.append(("show", project, br, lines))
        return ["line1", "line2"]

    # domain
    def set(self, project, br, dom):
        self.calls.append(("set", project, br, dom))

    def remove(self, project, br, dom):
        self.calls.append(("remove", project, br, dom))

    # upgrade / project
    def run(self, project, br, target_version=None):
        self.calls.append(("run", project, br, target_version))

    def info(self, project):
        self.calls.append(("info", project))
        return {"name": project, "version": "19.0"}


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeService:
    svc = FakeService()

    @contextmanager
    def fake_authed(rt, service_cls) -> Iterator[FakeService]:
        yield svc

    for mod in (branch, backup, domain, logs, upgrade, project):
        monkeypatch.setattr(mod, "authed_service", fake_authed)
    return svc


def test_branch_list(fake: FakeService) -> None:
    result = runner.invoke(app, [*P, "-o", "json", "branch", "list"])
    assert result.exit_code == 0
    assert "main" in result.stdout
    assert ("list_branches", "demo", None) in fake.calls


def test_branch_history_limit(fake: FakeService) -> None:
    result = runner.invoke(app, [*P, "branch", "history", "main", "--limit", "3"])
    assert result.exit_code == 0
    assert ("history", "demo", "main", 3) in fake.calls


def test_branch_rebuild_dry_run_does_not_call(fake: FakeService) -> None:
    result = runner.invoke(app, [*P, "--dry-run", "branch", "rebuild", "main"])
    assert result.exit_code == 0
    assert "would rebuild" in result.stdout
    assert fake.calls == []


def test_branch_rebuild_with_yes(fake: FakeService) -> None:
    result = runner.invoke(app, [*P, "--yes", "branch", "rebuild", "main"])
    assert result.exit_code == 0
    assert ("rebuild", "demo", "main") in fake.calls


def test_branch_delete_declined_aborts(fake: FakeService) -> None:
    result = runner.invoke(app, [*P, "branch", "delete", "main"], input="n\n")
    assert result.exit_code != 0  # Abort
    assert fake.calls == []


def test_branch_settings_read(fake: FakeService) -> None:
    result = runner.invoke(app, [*P, "-o", "json", "branch", "settings", "main"])
    assert result.exit_code == 0
    assert ("read_settings", "demo", "main") in fake.calls


def test_branch_settings_set(fake: FakeService) -> None:
    result = runner.invoke(app, [*P, "branch", "settings", "main", "--set", "worker_count=4"])
    assert result.exit_code == 0
    assert ("set_settings", "demo", "main", {"worker_count": "4"}) in fake.calls


def test_branch_settings_bad_pair(fake: FakeService) -> None:
    result = runner.invoke(app, [*P, "branch", "settings", "main", "--set", "nope"])
    assert result.exit_code != 0


def test_backup_list(fake: FakeService) -> None:
    result = runner.invoke(app, [*P, "-o", "json", "backup", "list", "main"])
    assert result.exit_code == 0
    assert ("list_backups", "demo", "main") in fake.calls


def test_backup_restore_is_destructive_and_needs_confirm(fake: FakeService) -> None:
    declined = runner.invoke(app, [*P, "backup", "restore", "main", "--from", "b1"], input="n\n")
    assert declined.exit_code != 0
    assert fake.calls == []
    ok = runner.invoke(app, [*P, "--yes", "backup", "restore", "main", "--from", "b1"])
    assert ok.exit_code == 0
    assert ("restore", "demo", "main", "b1") in fake.calls


def test_logs_show(fake: FakeService) -> None:
    result = runner.invoke(app, [*P, "-o", "plain", "logs", "show", "main"])
    assert result.exit_code == 0
    assert "line1" in result.stdout


def test_domain_set_dry_run(fake: FakeService) -> None:
    result = runner.invoke(app, [*P, "--dry-run", "domain", "set", "main", "ex.com"])
    assert result.exit_code == 0
    assert fake.calls == []


def test_upgrade_run_confirm(fake: FakeService) -> None:
    result = runner.invoke(app, [*P, "--yes", "upgrade", "run", "main"])
    assert result.exit_code == 0
    assert ("run", "demo", "main", None) in fake.calls


def test_project_info(fake: FakeService) -> None:
    result = runner.invoke(app, [*P, "-o", "json", "project", "info"])
    assert result.exit_code == 0
    assert ("info", "demo") in fake.calls


def test_missing_project_raises_config_error(fake: FakeService) -> None:
    # No --project and no env -> ConfigError (mapped to exit 2 by run() in the real CLI).
    from odoo_sh_cli.errors import ConfigError, ExitCode

    result = runner.invoke(app, ["branch", "list"])
    assert result.exit_code != 0
    assert isinstance(result.exception, ConfigError)
    assert result.exception.exit_code == ExitCode.USAGE


def test_backup_download_dry_run(fake: FakeService, tmp_path: Path) -> None:
    result = runner.invoke(
        app, [*P, "--dry-run", "backup", "download", "main", "--dest", str(tmp_path)]
    )
    assert result.exit_code == 0
    assert fake.calls == []
