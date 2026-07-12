"""UpgradeService — run and track upgrades."""

from __future__ import annotations

from typing import Any

from ..automation.browser_manager import BrowserManager
from ..automation.pages.upgrade_page import UpgradePage


class UpgradeService:
    def __init__(self, browser: BrowserManager) -> None:
        self._page = UpgradePage(browser.browser)

    def status(self, project: str, branch: str) -> dict[str, Any]:
        return self._page.status(project, branch)

    def run(self, project: str, branch: str, target_version: str | None = None) -> None:
        self._page.run(project, branch, target_version)
