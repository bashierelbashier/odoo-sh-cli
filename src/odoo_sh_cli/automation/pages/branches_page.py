"""BranchesPage — branch listing, build history, and branch actions.

Odoo.sh is a client-side app whose per-branch panels are addressable by URL
(verified 2026-07-02):

    /project/<p>/branches/<b>/history   build history
    /project/<p>/branches/<b>/settings  branch settings
    /project/<p>/builds/<b>             builds

Branches are listed in a sidebar grouped by stage (production / staging / dev).
The sidebar DOM is dynamic, so the reliable signal for branch identity is the
anchor ``href`` pointing at ``/project/<p>/branches/<name>``; stage is derived
from the enclosing ``[data-stage]`` container when present.

Action controls are visible-text buttons ("Rebuild", "Delete", "Connect", …).
These action selectors are best-effort and marked [VERIFY-ACTION]; they have not
been exercised against production data.
"""

from __future__ import annotations

import logging
from typing import Any

from ...errors import OperationFailedError, UITimeoutError
from .base_page import BasePage

logger = logging.getLogger(__name__)

SEL_BRANCH_ANCHOR = "a[href*='/branches/']"
# [VERIFY-ACTION] visible-text action controls on a branch:
TXT_REBUILD = "Rebuild"
TXT_DELETE = "Delete"
TXT_CONFIRM = "Confirm"


class BranchesPage(BasePage):
    def list_branches(self, project: str) -> list[dict[str, Any]]:
        """Return branches as ``{name, stage, url}`` dicts, deduped by name."""
        self.go_to(self.project_url(project))
        try:
            self.wait_visible(SEL_BRANCH_ANCHOR, timeout=20)
        except UITimeoutError:
            self.settle(3)  # empty projects or slow render — fall through to JS
        script = _LIST_BRANCHES_JS % {"project": project}
        rows: list[dict[str, Any]] = self.eval_js(script) or []
        return rows

    def branch_history(self, project: str, branch: str, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent builds/events for a branch (best-effort text rows)."""
        self.open_branch_panel(project, branch, "history")
        self.settle(2)
        rows: list[dict[str, Any]] = self.eval_js(_HISTORY_JS) or []
        return rows[:limit]

    def rebuild(self, project: str, branch: str) -> None:
        """Trigger a rebuild of the branch's build. [VERIFY-ACTION]"""
        self.open_branch_panel(project, branch, "history")
        if not self.is_visible(f'text="{TXT_REBUILD}"'):
            raise OperationFailedError(
                f"No 'Rebuild' control available for branch '{branch}' "
                "(it may be disabled while a build is running)."
            )
        self.click_text(TXT_REBUILD)
        # Odoo.sh may ask to confirm a production rebuild.
        self.settle(1)
        if self.is_visible(f'text="{TXT_CONFIRM}"'):
            self.click_text(TXT_CONFIRM)

    def delete(self, project: str, branch: str) -> None:
        """Delete a branch (and its build). Destructive. [VERIFY-ACTION]"""
        self.open_branch_panel(project, branch, "settings")
        if not self.is_visible(f'text="{TXT_DELETE}"'):
            raise OperationFailedError(f"No 'Delete' control found for branch '{branch}'.")
        self.click_text(TXT_DELETE)
        self.settle(1)
        if self.is_visible(f'text="{TXT_CONFIRM}"'):
            self.click_text(TXT_CONFIRM)

    def read_settings(self, project: str, branch: str) -> dict[str, Any]:
        self.open_branch_panel(project, branch, "settings")
        self.settle(2)
        data: dict[str, Any] = self.eval_js(_SETTINGS_JS) or {}
        return data

    def set_setting(self, project: str, branch: str, key: str, value: str) -> None:
        """Apply one key/value on the branch settings panel. [VERIFY-ACTION]

        Maps by the visible label; toggles checkboxes for on/off, fills text/number
        inputs and selects otherwise.
        """
        self.open_branch_panel(project, branch, "settings")
        self.settle(1)
        applied = self.eval_js(_SET_SETTING_JS % {"key": key, "value": value})
        if not applied:
            raise OperationFailedError(
                f"Could not find a settable control labelled '{key}' on branch settings."
            )
        if self.is_visible('text="Save"'):
            self.click_text("Save")

    def connection_info(self, project: str, branch: str) -> dict[str, Any]:
        """Read connection details (Git remote, SSH, etc.) from the branch view."""
        self.open_branch_panel(project, branch)
        self.settle(1)
        info: dict[str, Any] = self.eval_js(_CONNECT_JS) or {}
        return info


_LIST_BRANCHES_JS = r"""() => {
  const seen = new Set(); const out = [];
  const prefix = "/project/%(project)s/branches/";
  for (const a of document.querySelectorAll("a[href*='/branches/']")) {
    const href = a.getAttribute('href') || '';
    const i = href.indexOf('/branches/');
    if (i < 0) continue;
    let name = href.slice(i + '/branches/'.length).split('/')[0].split('?')[0];
    if (!name || seen.has(name)) continue;
    seen.add(name);
    let stage = null, n = a;
    for (let d = 0; n && d < 12; d++, n = n.parentElement) {
      if (n.getAttribute && n.getAttribute('data-stage')) { stage = n.getAttribute('data-stage'); break; }
    }
    out.push({name, stage, url: 'https://www.odoo.sh' + prefix + name});
  }
  return out;
}"""

_HISTORY_JS = r"""() => {
  const CHROME = new Set(['Branches','Builds','Status','Audit Logs','Settings','Documentation',
    'FAQ','HISTORY','SHELL','EDITOR','MONITOR','LOGS','BACKUPS','UPGRADE','TOOLS','SETTINGS',
    'Clone','Fork','Merge','SSH','SQL','Submodule','Delete','GitHub','HOME','FEATURES','PRICING',
    'BUY','DOCUMENTATION']);
  const rows = [], seen = new Set();
  // Prefer explicit history/build containers; fall back to timeline-ish list items.
  const scopes = document.querySelectorAll(
    "[class*='history'] li, [class*='timeline'] li, [class*='build'] li, .o_sh_history li");
  const items = scopes.length ? scopes : document.querySelectorAll('li');
  for (const li of items) {
    const t = (li.innerText || '').replace(/\s+/g, ' ').trim();
    if (!t || t.length < 4 || t.length > 240 || CHROME.has(t) || seen.has(t)) continue;
    seen.add(t);
    rows.push({event: t});
    if (rows.length >= 60) break;
  }
  return rows;
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
    out[k] = v;
  }
  return out;
}"""

_SET_SETTING_JS = r"""() => {
  const key = "%(key)s".toLowerCase(), value = "%(value)s";
  for (const row of document.querySelectorAll('tr, .form-group, [class*="row"]')) {
    const label = row.querySelector('label, th, .col-form-label');
    if (!label || !(label.innerText||'').toLowerCase().includes(key)) continue;
    const field = row.querySelector('input, select, textarea');
    if (!field) continue;
    if (field.type === 'checkbox') {
      const want = ['on','true','1','yes'].includes(value.toLowerCase());
      if (field.checked !== want) field.click();
    } else if (field.tagName === 'SELECT') {
      field.value = value; field.dispatchEvent(new Event('change', {bubbles:true}));
    } else {
      field.value = value; field.dispatchEvent(new Event('input', {bubbles:true}));
      field.dispatchEvent(new Event('change', {bubbles:true}));
    }
    return true;
  }
  return false;
}"""

_CONNECT_JS = r"""() => {
  const grab = re => {
    for (const el of document.querySelectorAll('input, code, pre, span')) {
      const v = (el.value || el.innerText || '').trim();
      if (re.test(v)) return v.slice(0, 200);
    }
    return null;
  };
  return {
    git: grab(/git@github\.com|https:\/\/github\.com/),
    ssh: grab(/@.*\.odoo\.com|ssh /),
  };
}"""
