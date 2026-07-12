"""Shared Page Object behavior: navigation, URL building, waits, failure shots.

Concrete pages subclass this and add intention-revealing methods. All selectors
and URLs live in the page subclasses (or here for cross-page constants), never
in services or commands.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path
from typing import Any

from ...errors import UITimeoutError

logger = logging.getLogger(__name__)

ODOO_SH_BASE = "https://www.odoo.sh"


class BasePage:
    def __init__(self, browser: Any) -> None:
        # ``browser`` is the rpaframework Browser instance from BrowserManager.
        self.browser = browser

    # -- navigation ------------------------------------------------------

    def project_url(self, project: str, *segments: str) -> str:
        """Build a project URL, e.g. ``.../project/<project>/settings``.

        Verified routing (2026-07-02): ``/project/<p>``, ``/project/<p>/settings``,
        ``/project/<p>/status``, ``/project/<p>/logs``, ``/project/<p>/builds/<b>``.
        """
        parts = [ODOO_SH_BASE, "project", project, *segments]
        return "/".join(p.strip("/") for p in parts)

    def branch_url(self, project: str, branch: str, *segments: str) -> str:
        """Build a branch panel URL.

        Verified routing (2026-07-02): ``/project/<p>/branches/<b>/<panel>`` where
        panel is one of history, monitor, logs, backups, upgrade, tools, settings.
        """
        return self.project_url(project, "branches", branch, *segments)

    def go_to(self, url: str) -> None:
        logger.debug("navigating to %s", url)
        self.browser.go_to(url)

    def open_branch_panel(self, project: str, branch: str, panel: str = "") -> None:
        """Navigate to a branch panel and give the SPA a moment to render it."""
        self.go_to(self.branch_url(project, branch, panel))
        self.settle()

    def settle(self, seconds: float = 2.0) -> None:
        """Best-effort wait for the single-page app to render panel content.

        The Odoo.sh UI is a client-side app that swaps panels without a full page
        load, so there is no navigation event to await; a short settle is the
        pragmatic option. Prefer :meth:`wait_visible` on a known marker where one
        exists.
        """
        import time

        time.sleep(seconds)

    # -- extraction ------------------------------------------------------

    def eval_js(self, script: str) -> Any:
        """Run a JS expression in the page and return the (JSON-able) result.

        Extraction snippets count as selectors and therefore live in Page Objects
        only. ``script`` must be a JS arrow function taking no args.
        """
        return self.browser.evaluate_javascript(None, script)

    def click_text(self, text: str) -> None:
        """Click the first element whose visible text matches ``text`` exactly."""
        self.browser.click(f'text="{text}"')

    def current_url(self) -> str:
        return str(self.browser.get_url())

    # -- waits / assertions ---------------------------------------------

    def wait_visible(self, selector: str, *, timeout: float | None = None) -> None:
        """Wait for an element to be visible, mapping failure to UITimeoutError.

        ``wait_for_elements_state`` defaults to the ``visible`` state, so we omit
        it. ``timeout`` is in seconds and converted to the ``timedelta`` the
        keyword expects; ``None`` uses the browser's configured timeout.
        """
        kwargs = {"timeout": timedelta(seconds=timeout)} if timeout is not None else {}
        try:
            self.browser.wait_for_elements_state(selector, **kwargs)
        except Exception as exc:  # AssertionError/TimeoutError from the browser lib
            raise UITimeoutError(f"Element not visible: {selector}") from exc

    def is_visible(self, selector: str) -> bool:
        try:
            state = self.browser.get_element_states(selector)
            return "visible" in state
        except Exception:
            return False

    # -- diagnostics -----------------------------------------------------

    def screenshot(self, dest: Path) -> None:
        """Capture a screenshot for failure diagnostics (secrets are scrubbed by logs)."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        self.browser.take_screenshot(filename=str(dest))
