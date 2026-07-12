"""Encrypted persistence of the Playwright browser session (spec §5.3).

The browser "storage state" (cookies + localStorage) is what lets us skip the
fragile GitHub login on subsequent runs. It contains session cookies, so it is
treated as a secret: serialized to JSON, encrypted with Fernet, and written
``0600`` under the user config dir. The Fernet key is a machine-local key kept
in the OS keyring — never in the repo or alongside the session file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from .config import KEYRING_SERVICE
from .errors import AuthenticationError

DEFAULT_SESSION_PATH = Path.home() / ".config" / "odoo-sh-cli" / "session.enc"
_KEYRING_KEY_NAME = "session_encryption_key"


class SessionStore:
    """Save/load the encrypted Playwright storage state."""

    def __init__(self, path: Path | None = None, service: str = KEYRING_SERVICE) -> None:
        self.path = path or DEFAULT_SESSION_PATH
        self.service = service

    def _fernet(self) -> Fernet:
        import keyring

        key = keyring.get_password(self.service, _KEYRING_KEY_NAME)
        if not key:
            key = Fernet.generate_key().decode()
            keyring.set_password(self.service, _KEYRING_KEY_NAME, key)
        return Fernet(key.encode())

    def exists(self) -> bool:
        return self.path.exists()

    def save(self, storage_state: dict[str, Any]) -> None:
        """Encrypt and write the storage state with ``0600`` permissions."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        token = self._fernet().encrypt(json.dumps(storage_state).encode())
        # Create with restrictive perms from the start (avoid a readable window).
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(token)
        os.chmod(self.path, 0o600)

    def load(self) -> dict[str, Any]:
        """Decrypt and return the stored storage state.

        Raises :class:`AuthenticationError` if the file is missing or cannot be
        decrypted (corrupt, or key rotated) so callers fall back to full login.
        """
        if not self.path.exists():
            raise AuthenticationError("No saved session. Run 'odoo-sh auth login'.")
        try:
            data = self._fernet().decrypt(self.path.read_bytes())
        except (InvalidToken, ValueError) as exc:
            raise AuthenticationError(
                "Saved session could not be decrypted; please log in again."
            ) from exc
        state: dict[str, Any] = json.loads(data)
        return state

    def clear(self) -> bool:
        """Delete the session file. Returns True if a file was removed."""
        if self.path.exists():
            self.path.unlink()
            return True
        return False
