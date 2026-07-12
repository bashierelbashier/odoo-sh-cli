"""BranchService — branch operations in domain terms."""

from __future__ import annotations

from typing import Any

from ..automation.browser_manager import BrowserManager
from ..automation.pages.branches_page import BranchesPage


class BranchService:
    def __init__(self, browser: BrowserManager) -> None:
        self._page = BranchesPage(browser.browser)

    def list_branches(self, project: str, stage: str | None = None) -> list[dict[str, Any]]:
        rows = self._page.list_branches(project)
        if stage:
            rows = [r for r in rows if (r.get("stage") or "").lower() == stage.lower()]
        return rows

    def history(self, project: str, branch: str, limit: int = 20) -> list[dict[str, Any]]:
        return self._page.branch_history(project, branch, limit)

    def rebuild(self, project: str, branch: str) -> None:
        self._page.rebuild(project, branch)

    def delete(self, project: str, branch: str) -> None:
        self._page.delete(project, branch)

    def read_settings(self, project: str, branch: str) -> dict[str, Any]:
        return self._page.read_settings(project, branch)

    def set_settings(self, project: str, branch: str, pairs: dict[str, str]) -> dict[str, Any]:
        for key, value in pairs.items():
            self._page.set_setting(project, branch, key, value)
        return self._page.read_settings(project, branch)

    def connection_info(self, project: str, branch: str) -> dict[str, Any]:
        return self._page.connection_info(project, branch)
