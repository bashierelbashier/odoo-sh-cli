"""AuthService — login, session reuse, status, logout (spec §5.4).

The service speaks in domain terms and delegates all clicking to
:class:`LoginPage`. It registers the loaded secrets with the scrubber before
they can ever be logged, then runs the numbered login flow.
"""

from __future__ import annotations

import logging

from ..automation.browser_manager import BrowserManager
from ..automation.pages.login_page import LoginPage
from ..config import Credentials, CredentialStore
from ..errors import AuthenticationError
from ..logging_setup import SecretScrubber
from ..session import SessionStore

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(
        self,
        browser: BrowserManager,
        credentials: CredentialStore | None = None,
        session_store: SessionStore | None = None,
    ) -> None:
        self.browser = browser
        self.credentials = credentials or CredentialStore()
        self.session_store = session_store or browser.session_store
        self._page = LoginPage(browser.browser)

    # -- public API ------------------------------------------------------

    def login(self) -> str:
        """Run the full login flow and persist the session. Returns the username."""
        creds = self.credentials.load()
        self._register_secrets(creds)
        self._run_login_flow(creds)
        self.browser.save_session()
        logger.info("authenticated as %s", creds.username)
        return creds.username

    def ensure_session(self) -> None:
        """Reuse the saved session; verify it, and re-login exactly once if stale."""
        if self._page.is_logged_in():
            return
        logger.debug("session invalid or absent; performing full login")
        self.login()
        if not self._page.is_logged_in():
            raise AuthenticationError("Login succeeded but session verification failed.")

    def status(self) -> bool:
        """Return True if the current (restored) session is valid."""
        return self._page.is_logged_in()

    def logout(self) -> bool:
        """Delete the persisted session. Returns True if a session was removed."""
        return self.session_store.clear()

    # -- internals -------------------------------------------------------

    def _register_secrets(self, creds: Credentials) -> None:
        SecretScrubber.register(creds.password, creds.totp_secret)

    def _run_login_flow(self, creds: Credentials) -> None:
        page = self._page
        # Navigating to the project area redirects to GitHub login when logged out,
        # or stays on Odoo.sh if a restored session is still valid.
        page.open()

        if page.on_github_login():
            page.submit_github_credentials(creds.username, creds.password)

            if page.needs_two_factor():
                if not creds.totp_secret:
                    raise AuthenticationError(
                        "GitHub asked for a 2FA code but no TOTP secret is configured."
                    )
                page.submit_two_factor(creds.totp_secret)

            if page.needs_authorization():
                page.authorize()

        page.wait_for_dashboard()
