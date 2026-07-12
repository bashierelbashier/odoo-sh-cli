"""ProjectPage — project-level info and settings.

URLs (verified): ``/project/<p>`` (overview: name, repo, version, status,
license) and ``/project/<p>/settings`` (project settings). The overview exposes
key/value facts (License, Status, Version, Location) which we parse. Generic
settings mutation and the commit-status-token field are best-effort
[VERIFY-ACTION]; the token is treated as a secret.
"""

from __future__ import annotations

import logging
from typing import Any

from ...errors import OperationFailedError
from .base_page import BasePage

logger = logging.getLogger(__name__)

TXT_SAVE = "Save"
# [VERIFY-ACTION] commit-status-token field on the project settings page:
SEL_TOKEN_INPUT = "input[name*='token' i], input[placeholder*='token' i]"


class ProjectPage(BasePage):
    def info(self, project: str) -> dict[str, Any]:
        self.go_to(self.project_url(project))
        self.settle(2)
        info: dict[str, Any] = self.eval_js(_INFO_JS % {"project": project}) or {}
        info.setdefault("name", project)
        return info

    def settings(self, project: str) -> dict[str, Any]:
        self.go_to(self.project_url(project, "settings"))
        self.settle(2)
        data: dict[str, Any] = self.eval_js(_SETTINGS_JS) or {}
        return data

    def set_commit_status_token(self, project: str, token: str) -> None:
        """Set/rotate the commit status token. [VERIFY-ACTION]"""
        self.go_to(self.project_url(project, "settings"))
        self.settle(1)
        if not self.is_visible(SEL_TOKEN_INPUT):
            raise OperationFailedError("No commit-status-token field on project settings.")
        self.browser.fill_secret(SEL_TOKEN_INPUT, token)
        if self.is_visible(f'text="{TXT_SAVE}"'):
            self.click_text(TXT_SAVE)


_INFO_JS = r"""() => {
  const out = {};
  const text = document.body.innerText;
  // Label/value facts (tab- or colon-separated), when present on the overview.
  for (const key of ['License','Status','Version','Location']) {
    const m = text.match(new RegExp(key + '[ \\t:]+([^\\n]+)'));
    if (m) out[key.toLowerCase()] = m[1].trim().slice(0, 60);
  }
  // Linked GitHub repo appears as "(<owner>/<repo>)".
  const repo = text.match(/\(([\w.-]+\/[\w.-]+)\)/);
  if (repo) out.repo = repo[1];
  // Fallbacks from the single-project page.
  if (!out.version) { const v = text.match(/\b(\d+\.\d+)\b/); if (v) out.version = v[1]; }
  const trial = text.match(/trial period[^.]*\./i);
  if (trial) out.note = trial[0].trim().slice(0, 120);
  return out;
}"""

_SETTINGS_JS = r"""() => {
  const out = {};
  for (const row of document.querySelectorAll('tr, .form-group, [class*="row"]')) {
    const label = row.querySelector('label, th, .col-form-label');
    const field = row.querySelector('input, select, textarea, td');
    if (!label) continue;
    const k = (label.innerText||'').replace(/\s+/g,' ').trim();
    if (!k || k.length > 60) continue;
    let v = '';
    if (field) {
      if (field.type === 'checkbox') v = field.checked;
      else v = (field.value || field.innerText || '').replace(/\s+/g,' ').trim().slice(0,80);
    }
    if (k) out[k] = v;
  }
  return out;
}"""
