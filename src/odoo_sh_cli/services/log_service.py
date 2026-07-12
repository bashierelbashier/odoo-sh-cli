"""LogService — read and monitor branch logs."""

from __future__ import annotations

from collections.abc import Iterator

from ..automation.browser_manager import BrowserManager
from ..automation.pages.logs_page import LogsPage


class LogService:
    def __init__(self, browser: BrowserManager) -> None:
        self._page = LogsPage(browser.browser)

    def show(self, project: str, branch: str, lines: int | None = None) -> list[str]:
        return self._page.read_lines(project, branch, lines)

    def monitor(
        self,
        project: str,
        branch: str,
        *,
        interval: float,
        stop: object | None = None,
    ) -> Iterator[str]:
        """Yield new log lines as they appear until interrupted.

        ``stop`` is an optional ``threading.Event``-like object; when set, the
        generator returns. Interruption is otherwise via KeyboardInterrupt in the
        command layer.
        """
        import time

        seen: set[str] = set()
        first = True
        # Prime with the current tail so we don't dump the whole history first.
        current = self._page.read_lines(project, branch)
        for line in current:
            seen.add(line)
        while not (stop is not None and getattr(stop, "is_set", lambda: False)()):
            lines = current if first else self._page.read_lines_current()
            first = False
            for line in lines:
                if line not in seen:
                    seen.add(line)
                    yield line
            time.sleep(interval)
