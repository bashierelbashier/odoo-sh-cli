"""ProjectService — project-level info and settings."""

from __future__ import annotations

from typing import Any

from ..automation.browser_manager import BrowserManager
from ..automation.pages.project_page import ProjectPage
from ..logging_setup import SecretScrubber


class ProjectService:
    def __init__(self, browser: BrowserManager) -> None:
        self._page = ProjectPage(browser.browser)

    def info(self, project: str) -> dict[str, Any]:
        return self._page.info(project)

    def settings(self, project: str) -> dict[str, Any]:
        return self._page.settings(project)

    def set_commit_status_token(self, project: str, token: str) -> None:
        SecretScrubber.register(token)  # never let the token reach logs
        self._page.set_commit_status_token(project, token)
