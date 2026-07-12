"""DomainsPage — manage a branch instance's custom domains.

On Odoo.sh, custom domains are configured in the branch **Settings** panel
(``/project/<p>/branches/<b>/settings``) under a "Custom domains" section. The
exact input/table selectors are best-effort [VERIFY-ACTION]; no domain was
added/removed on the real project.
"""

from __future__ import annotations

import logging
from typing import Any

from ...errors import OperationFailedError
from .base_page import BasePage

logger = logging.getLogger(__name__)

TXT_ADD = "Add"
TXT_SAVE = "Save"
TXT_CONFIRM = "Confirm"
# [VERIFY-ACTION] domain input field within the settings panel:
SEL_DOMAIN_INPUT = "input[placeholder*='domain' i], input[name*='domain' i]"


class DomainsPage(BasePage):
    def list_domains(self, project: str, branch: str) -> list[dict[str, Any]]:
        self.open_branch_panel(project, branch, "settings")
        self.settle(2)
        rows: list[dict[str, Any]] = self.eval_js(_DOMAINS_JS) or []
        return rows

    def set_domain(self, project: str, branch: str, domain: str) -> None:
        """Add/configure a custom domain. [VERIFY-ACTION]"""
        self.open_branch_panel(project, branch, "settings")
        self.settle(1)
        if not self.is_visible(SEL_DOMAIN_INPUT):
            raise OperationFailedError("No domain input found in branch settings.")
        self.browser.fill_text(SEL_DOMAIN_INPUT, domain)
        for label in (TXT_ADD, TXT_SAVE):
            if self.is_visible(f'text="{label}"'):
                self.click_text(label)
                break

    def remove_domain(self, project: str, branch: str, domain: str) -> None:
        """Remove a configured domain. [VERIFY-ACTION]"""
        self.open_branch_panel(project, branch, "settings")
        self.settle(1)
        removed = self.eval_js(_REMOVE_DOMAIN_JS % {"domain": domain})
        if not removed:
            raise OperationFailedError(f"Domain '{domain}' not found or no remove control.")
        self.settle(1)
        if self.is_visible(f'text="{TXT_CONFIRM}"'):
            self.click_text(TXT_CONFIRM)


_DOMAINS_JS = r"""() => {
  const out = [], seen = new Set();
  const re = /^[a-z0-9.-]+\.[a-z]{2,}$/i;
  for (const el of document.querySelectorAll("input, td, span, code")) {
    const v = (el.value || el.innerText || '').trim();
    if (re.test(v) && !v.endsWith('.odoo.com') && !seen.has(v)) { seen.add(v); out.push({domain: v}); }
  }
  return out;
}"""

_REMOVE_DOMAIN_JS = r"""() => {
  const target = "%(domain)s";
  for (const row of document.querySelectorAll('tr, li, div')) {
    if ((row.innerText||'').includes(target)) {
      const btn = row.querySelector("button, a.btn, [class*='delete'], [class*='remove'], .fa-trash");
      if (btn) { btn.click(); return true; }
    }
  }
  return false;
}"""
