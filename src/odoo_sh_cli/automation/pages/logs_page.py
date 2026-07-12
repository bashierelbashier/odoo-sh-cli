"""LogsPage — read and monitor a branch's logs.

Panel URL (verified): ``/project/<p>/branches/<b>/logs``. The panel renders log
lines in a scrollable region; we extract visible lines as text. Monitoring polls
the same panel and yields lines not seen before.
"""

from __future__ import annotations

import logging

from .base_page import BasePage

logger = logging.getLogger(__name__)


class LogsPage(BasePage):
    def read_lines(self, project: str, branch: str, lines: int | None = None) -> list[str]:
        self.open_branch_panel(project, branch, "logs")
        self.settle(2)
        result: list[str] = self.eval_js(_LOGS_JS) or []
        if lines is not None and lines > 0:
            return result[-lines:]
        return result

    def read_lines_current(self) -> list[str]:
        """Re-read log lines without navigating (used while monitoring)."""
        result: list[str] = self.eval_js(_LOGS_JS) or []
        return result


_LOGS_JS = r"""() => {
  const out = [];
  const containers = document.querySelectorAll(
    "[class*='log'] pre, pre[class*='log'], [class*='console'], .o_sh_log, pre, code");
  for (const c of containers) {
    const txt = (c.innerText || '');
    for (const line of txt.split('\n')) {
      const t = line.replace(/\s+$/,'');
      if (t.trim()) out.push(t);
    }
    if (out.length >= 2000) break;
  }
  return out;
}"""
