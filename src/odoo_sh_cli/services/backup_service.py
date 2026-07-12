"""BackupService — backup lifecycle in domain terms."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..automation.browser_manager import BrowserManager
from ..automation.pages.backups_page import BackupsPage


class BackupService:
    def __init__(self, browser: BrowserManager) -> None:
        self._page = BackupsPage(browser.browser)

    def list_backups(self, project: str, branch: str) -> list[dict[str, Any]]:
        return self._page.list_backups(project, branch)

    def create(self, project: str, branch: str, comment: str | None = None) -> None:
        self._page.create_backup(project, branch, comment)

    def download(self, project: str, branch: str, dest: Path, backup_id: str | None = None) -> Path:
        return self._page.download_backup(project, branch, dest, backup_id)

    def restore(self, project: str, branch: str, backup_ref: str) -> None:
        self._page.restore_backup(project, branch, backup_ref)
