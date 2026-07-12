"""BackupsPage — list / create / download / restore backups.

Panel URL (verified): ``/project/<p>/branches/<b>/backups``. Observed controls:
"Create Backup" and "Import Database" buttons; per-backup rows expose download
and restore actions.

Create/download/restore action selectors are best-effort [VERIFY-ACTION]; they
were not executed against the real project to avoid mutating production data.
Download uses robotframework-browser's download-promise pattern.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ...errors import OperationFailedError
from .base_page import BasePage

logger = logging.getLogger(__name__)

TXT_CREATE_BACKUP = "Create Backup"
TXT_IMPORT_DATABASE = "Import Database"
TXT_CONFIRM = "Confirm"
# [VERIFY-ACTION] per-row controls:
TXT_DOWNLOAD = "Download"
TXT_RESTORE = "Restore"


class BackupsPage(BasePage):
    def list_backups(self, project: str, branch: str) -> list[dict[str, Any]]:
        self.open_branch_panel(project, branch, "backups")
        self.settle(2)
        rows: list[dict[str, Any]] = self.eval_js(_BACKUPS_JS) or []
        return rows

    def create_backup(self, project: str, branch: str, comment: str | None = None) -> None:
        self.open_branch_panel(project, branch, "backups")
        if not self.is_visible(f'text="{TXT_CREATE_BACKUP}"'):
            raise OperationFailedError("No 'Create Backup' control on the backups panel.")
        self.click_text(TXT_CREATE_BACKUP)
        self.settle(1)
        if comment and self.is_visible("textarea, input[type='text']"):
            self.browser.fill_text("textarea, input[type='text']", comment)
        if self.is_visible(f'text="{TXT_CONFIRM}"'):
            self.click_text(TXT_CONFIRM)

    def download_backup(
        self, project: str, branch: str, dest: Path, backup_id: str | None = None
    ) -> Path:
        """Download a backup artifact to ``dest``; returns the saved file path.

        [VERIFY-ACTION] Uses ``Promise To Wait For Download`` + click, then saves
        the downloaded file to ``dest``.
        """
        self.open_branch_panel(project, branch, "backups")
        self.settle(2)
        if not self.is_visible(f'text="{TXT_DOWNLOAD}"'):
            raise OperationFailedError("No 'Download' control on the backups panel.")
        promise = self.browser.promise_to_wait_for_download(saveAs=str(dest))
        self.click_text(TXT_DOWNLOAD)
        result = self.browser.wait_for(promise)
        saved = result.get("saveAs") if isinstance(result, dict) else None
        return Path(saved or dest)

    def restore_backup(self, project: str, branch: str, backup_ref: str) -> None:
        """Restore a backup onto the branch. Destructive. [VERIFY-ACTION]"""
        self.open_branch_panel(project, branch, "backups")
        self.settle(2)
        if not self.is_visible(f'text="{TXT_RESTORE}"'):
            raise OperationFailedError("No 'Restore' control on the backups panel.")
        self.click_text(TXT_RESTORE)
        self.settle(1)
        if self.is_visible(f'text="{TXT_CONFIRM}"'):
            self.click_text(TXT_CONFIRM)


_BACKUPS_JS = r"""() => {
  const rows = [];
  const tables = document.querySelectorAll("table tbody tr, [class*='backup'] li, [class*='backup'] tr");
  for (const tr of tables) {
    const cells = [...tr.querySelectorAll('td')].map(td => (td.innerText||'').replace(/\s+/g,' ').trim());
    const text = (tr.innerText||'').replace(/\s+/g,' ').trim();
    if (!text || text.length < 3) continue;
    rows.push(cells.length ? {cells, text} : {text});
    if (rows.length >= 100) break;
  }
  return rows;
}"""
