"""AuthService orchestration with the browser/page layer faked (spec §5.4)."""

from __future__ import annotations

import pyotp
import pytest

from odoo_sh_cli.config import Credentials
from odoo_sh_cli.errors import AuthenticationError
from odoo_sh_cli.logging_setup import REDACTION, SecretScrubber
from odoo_sh_cli.services import auth_service
from odoo_sh_cli.services.auth_service import AuthService

CREDS = Credentials(username="bot", password="s3cr3t", totp_secret=pyotp.random_base32())


class FakeLoginPage:
    """Records the flow and simulates GitHub's conditional screens."""

    def __init__(self, browser: object) -> None:
        self.calls: list[str] = []
        self.logged_in = False
        self.at_github_login = True  # logged-out default: /project redirects to GitHub
        self.require_2fa = False
        self.require_authorize = False
        self.submitted_username: str | None = None
        self.submitted_2fa = False

    def is_logged_in(self) -> bool:
        return self.logged_in

    def open(self) -> None:
        self.calls.append("open")

    def on_github_login(self) -> bool:
        return self.at_github_login

    def submit_github_credentials(self, username: str, password: str) -> None:
        self.calls.append("submit_credentials")
        self.submitted_username = username

    def needs_two_factor(self) -> bool:
        return self.require_2fa

    def submit_two_factor(self, totp_secret: str) -> None:
        self.calls.append("submit_2fa")
        self.submitted_2fa = True

    def needs_authorization(self) -> bool:
        return self.require_authorize

    def authorize(self) -> None:
        self.calls.append("authorize")

    def wait_for_dashboard(self) -> None:
        self.calls.append("wait_for_dashboard")
        self.logged_in = True
        self.at_github_login = False


class FakeBrowserManager:
    def __init__(self) -> None:
        self.browser = object()
        self.saved = False

    def save_session(self) -> None:
        self.saved = True


@pytest.fixture
def patched_page(monkeypatch: pytest.MonkeyPatch) -> type[FakeLoginPage]:
    monkeypatch.setattr(auth_service, "LoginPage", FakeLoginPage)
    return FakeLoginPage


class StaticCreds:
    def __init__(self, creds: Credentials) -> None:
        self._creds = creds

    def load(self) -> Credentials:
        return self._creds


def _service(**page_flags: bool) -> tuple[AuthService, FakeBrowserManager]:
    browser = FakeBrowserManager()
    svc = AuthService(browser, credentials=StaticCreds(CREDS), session_store=object())  # type: ignore[arg-type]
    for key, value in page_flags.items():
        setattr(svc._page, key, value)
    return svc, browser


def test_full_login_no_2fa(patched_page: type[FakeLoginPage]) -> None:
    svc, browser = _service()
    username = svc.login()
    assert username == "bot"
    assert svc._page.calls == [
        "open",
        "submit_credentials",
        "wait_for_dashboard",
    ]
    assert browser.saved is True


def test_login_with_2fa_and_authorize(patched_page: type[FakeLoginPage]) -> None:
    svc, _ = _service(require_2fa=True, require_authorize=True)
    svc.login()
    assert svc._page.submitted_2fa is True
    assert "authorize" in svc._page.calls


def test_login_2fa_without_secret_raises(patched_page: type[FakeLoginPage]) -> None:
    creds = Credentials(username="bot", password="p", totp_secret=None)
    browser = FakeBrowserManager()
    svc = AuthService(browser, credentials=StaticCreds(creds), session_store=object())  # type: ignore[arg-type]
    svc._page.require_2fa = True
    with pytest.raises(AuthenticationError):
        svc.login()


def test_ensure_session_reuses_valid_session(patched_page: type[FakeLoginPage]) -> None:
    svc, browser = _service(logged_in=True)
    svc.ensure_session()
    # No login flow ran, nothing saved.
    assert svc._page.calls == []
    assert browser.saved is False


def test_ensure_session_relogins_when_invalid(patched_page: type[FakeLoginPage]) -> None:
    svc, browser = _service(logged_in=False)
    svc.ensure_session()
    assert "wait_for_dashboard" in svc._page.calls
    assert browser.saved is True


def test_login_registers_secrets_for_scrubbing(patched_page: type[FakeLoginPage]) -> None:
    svc, _ = _service()
    svc.login()
    assert SecretScrubber.scrub("leak s3cr3t here") == f"leak {REDACTION} here"
