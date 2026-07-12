"""UpgradePage — run and track database upgrades.

Panel URL (verified): ``/project/<p>/branches/<b>/upgrade``. Action controls are
best-effort [VERIFY-ACTION]; the upgrade trigger and status text were not
exercised against the real project.
"""

from __future__ import annotations

import logging
from typing import Any

from ...errors import OperationFailedError
from .base_page import BasePage

logger = logging.getLogger(__name__)

TXT_UPGRADE = "Upgrade"
TXT_START = "Start"
TXT_CONFIRM = "Confirm"


class UpgradePage(BasePage):
    def status(self, project: str, branch: str) -> dict[str, Any]:
        self.open_branch_panel(project, branch, "upgrade")
        self.settle(2)
        info: dict[str, Any] = self.eval_js(_UPGRADE_STATUS_JS) or {}
        return info

    def run(self, project: str, branch: str, target_version: str | None = None) -> None:
        """Trigger an upgrade. [VERIFY-ACTION]"""
        self.open_branch_panel(project, branch, "upgrade")
        self.settle(1)
        control = next(
            (t for t in (TXT_START, TXT_UPGRADE) if self.is_visible(f'text="{t}"')), None
        )
        if control is None:
            raise OperationFailedError("No upgrade trigger control on the upgrade panel.")
        self.click_text(control)
        self.settle(1)
        if self.is_visible(f'text="{TXT_CONFIRM}"'):
            self.click_text(TXT_CONFIRM)


_UPGRADE_STATUS_JS = r"""() => {
  const body = (document.querySelector("[class*='upgrade']") || document.body).innerText || '';
  const text = body.replace(/\n{2,}/g,'\n').trim().slice(0, 800);
  return {panel: text};
}"""
