"""Exception hierarchy and exit-code mapping.

Exit codes (spec §6.3):
    0  success
    1  generic/unexpected error
    2  usage error (bad args) — handled by Typer
    3  authentication error
    4  operation failed on Odoo.sh side
    5  timeout / element not found (likely UI drift)
"""

from __future__ import annotations


class ExitCode:
    """Named exit codes. Kept as ints so they can be returned directly."""

    SUCCESS = 0
    GENERIC = 1
    USAGE = 2
    AUTH = 3
    OPERATION = 4
    UI_TIMEOUT = 5


class OdooShError(Exception):
    """Base class for all expected, user-facing errors.

    Carries an ``exit_code`` so the CLI entry point can translate any raised
    error into the correct process exit status without a big ``isinstance``
    ladder.
    """

    exit_code: int = ExitCode.GENERIC

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ConfigError(OdooShError):
    """Bad or missing configuration (e.g., no project set)."""

    exit_code = ExitCode.USAGE


class AuthenticationError(OdooShError):
    """Login failed, session invalid/expired, or credentials missing."""

    exit_code = ExitCode.AUTH


class OperationFailedError(OdooShError):
    """Odoo.sh refused or failed an operation (e.g., production rebuild guard)."""

    exit_code = ExitCode.OPERATION


class UITimeoutError(OdooShError):
    """A required element never appeared / an action timed out (likely UI drift)."""

    exit_code = ExitCode.UI_TIMEOUT


# Backwards-friendly alias — the spec names both ElementNotFoundError and UITimeoutError.
ElementNotFoundError = UITimeoutError
