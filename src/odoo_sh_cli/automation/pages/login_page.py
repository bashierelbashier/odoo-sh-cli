"""LoginPage — the GitHub -> Odoo.sh login flow.

VERIFIED against the live UI (2026-07-02) with a real service account:

* Navigating to ``https://www.odoo.sh/project`` while logged out redirects
  straight to ``github.com/login`` with Odoo.sh's OAuth ``client_id`` — there is
  **no** intermediate "Log in with GitHub" button to click.
* GitHub login uses the stable ``#login_field`` / ``#password`` inputs and the
  ``input.js-sign-in-button`` submit control.
* For a pre-authorized account, submitting credentials lands directly back on
  ``https://www.odoo.sh/project`` — no 2FA prompt and no OAuth "Authorize"
  screen. The 2FA / authorize handling below is kept defensively for accounts
  that do present them.
* Logged-in marker: we are on an ``odoo.sh`` URL (not redirected to github.com)
  and the ``/web/login`` "Sign in" link is absent.
"""

from __future__ import annotations

import logging
import time

import pyotp

from ...errors import AuthenticationError
from ...logging_setup import SecretScrubber
from .base_page import BasePage

logger = logging.getLogger(__name__)

# -- Odoo.sh --------------------------------------------------------------
ODOO_SH_PROJECT_URL = "https://www.odoo.sh/project"
SEL_ODOO_SIGNIN_LINK = "a[href='/web/login']"  # present only when logged out

# -- GitHub ---------------------------------------------------------------
SEL_GH_USERNAME = "#login_field"
SEL_GH_PASSWORD = "#password"
SEL_GH_SUBMIT = "input.js-sign-in-button"
SEL_GH_OTP = "input[autocomplete='one-time-code'], #app_totp, #otp"
SEL_GH_OTP_SUBMIT = "button[type='submit']"
SEL_GH_AUTHORIZE = "button[name='authorize'][value='1']"


class LoginPage(BasePage):
    """Drives the multi-step login. Each step is a small, testable method."""

    def open(self) -> None:
        """Navigate to the project area; redirects to GitHub login if logged out."""
        self.go_to(ODOO_SH_PROJECT_URL)

    def _url(self) -> str:
        return str(self.browser.get_url())

    def is_logged_in(self) -> bool:
        """True if the (possibly session-restored) user is authenticated on Odoo.sh."""
        self.open()
        if "github.com" in self._url():
            return False
        return not self.is_visible(SEL_ODOO_SIGNIN_LINK)

    def on_github_login(self) -> bool:
        return "github.com" in self._url() and self.is_visible(SEL_GH_USERNAME)

    def submit_github_credentials(self, username: str, password: str) -> None:
        self.wait_visible(SEL_GH_USERNAME)
        self.browser.fill_text(SEL_GH_USERNAME, username)
        self.browser.fill_secret(SEL_GH_PASSWORD, password)
        self.browser.click(SEL_GH_SUBMIT)

    def needs_two_factor(self) -> bool:
        return self.is_visible(SEL_GH_OTP)

    def submit_two_factor(self, totp_secret: str) -> None:
        """Generate and submit a TOTP code. The code is registered for scrubbing."""
        code = pyotp.TOTP(totp_secret).now()
        SecretScrubber.register(code)
        self.browser.fill_secret(SEL_GH_OTP, code)
        self.browser.click(SEL_GH_OTP_SUBMIT)

    def needs_authorization(self) -> bool:
        """The OAuth 'Authorize <app>' screen (only if the account isn't pre-authorized)."""
        return self.is_visible(SEL_GH_AUTHORIZE)

    def authorize(self) -> None:
        self.browser.click(SEL_GH_AUTHORIZE)

    def wait_for_dashboard(self, *, timeout: float = 30.0) -> None:
        """Wait for the redirect back to Odoo.sh and confirm the logged-in marker."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            url = self._url()
            on_odoo = "odoo.sh" in url and "github.com" not in url
            if on_odoo and not self.is_visible(SEL_ODOO_SIGNIN_LINK):
                return
            time.sleep(1)
        raise AuthenticationError(
            "Login did not reach the Odoo.sh dashboard. If GitHub showed a CAPTCHA "
            "or device-verification prompt, re-run 'auth login --no-headless' to solve it once."
        )
