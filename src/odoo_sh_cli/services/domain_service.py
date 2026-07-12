"""DomainService — manage instance custom domains."""

from __future__ import annotations

from typing import Any

from ..automation.browser_manager import BrowserManager
from ..automation.pages.domains_page import DomainsPage


class DomainService:
    def __init__(self, browser: BrowserManager) -> None:
        self._page = DomainsPage(browser.browser)

    def list_domains(self, project: str, branch: str) -> list[dict[str, Any]]:
        return self._page.list_domains(project, branch)

    def set(self, project: str, branch: str, domain: str) -> None:
        self._page.set_domain(project, branch, domain)

    def remove(self, project: str, branch: str, domain: str) -> None:
        self._page.remove_domain(project, branch, domain)
