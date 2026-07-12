"""Owns the Playwright browser/context and bridges the encrypted session.

Uses ``RPA.Browser.Playwright`` (rpaframework), which subclasses
robotframework-browser's ``Browser``; its keywords are available as snake_case
Python methods (e.g. ``New Page`` -> ``new_page``).

Only Page Objects should call the browser directly — services go through them.
``BrowserManager`` exists to centralize launch options, session load/save, and
download handling.

Storage-state save/load keyword signatures were verified against
robotframework-browser 20.x on 2026-07-02 (see :func:`save_session`).
"""

from __future__ import annotations

import functools
import json
import logging
import tempfile
from pathlib import Path
from typing import Any

from ..config import Settings
from ..session import SessionStore

logger = logging.getLogger(__name__)

VIEWPORT = {"width": 1440, "height": 900}


@functools.lru_cache(maxsize=1)
def _wrapper_dir() -> Path:
    """Directory the robotframework-browser node wrapper runs in.

    ``save_storage_state()`` returns paths relative to this directory.
    """
    import Browser as browser_pkg

    return Path(browser_pkg.__file__).parent / "wrapper"


class BrowserManager:
    """Thin lifecycle wrapper around ``RPA.Browser.Playwright``."""

    def __init__(
        self,
        settings: Settings,
        session_store: SessionStore | None = None,
        download_dir: Path | None = None,
    ) -> None:
        self.settings = settings
        self.session_store = session_store or SessionStore()
        self.download_dir = download_dir or Path.cwd()
        self._browser: Any = None
        self._started = False

    # -- lifecycle -------------------------------------------------------

    def start(self) -> None:
        """Launch a browser + context + page, restoring a saved session if present."""
        if self._started:
            return
        from RPA.Browser.Playwright import Browser

        self._browser = Browser()
        self._browser.new_browser(headless=self.settings.headless)
        self._browser.new_context(**self._context_kwargs())
        self._browser.new_page()
        self._browser.set_browser_timeout(f"{self.settings.timeout}s")
        self._started = True
        logger.debug("browser started (headless=%s)", self.settings.headless)

    def _context_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "viewport": VIEWPORT,
            "acceptDownloads": True,
        }
        state = self._load_state_file()
        if state is not None:
            # robotframework-browser accepts a path to a storage-state JSON file.
            kwargs["storageState"] = str(state)
        return kwargs

    def _load_state_file(self) -> Path | None:
        """Decrypt the saved session into a temp JSON file for Playwright to load."""
        if not (self.settings.persist_session and self.session_store.exists()):
            return None
        try:
            state = self.session_store.load()
        except Exception:  # missing/corrupt -> just log in fresh
            logger.debug("no usable saved session; starting fresh")
            return None
        fd, name = tempfile.mkstemp(suffix=".json", prefix="odoo_sh_state_")
        path = Path(name)
        with open(fd, "w") as fh:
            json.dump(state, fh)
        self._state_temp = path  # kept for cleanup on close()
        return path

    def save_session(self) -> None:
        """Persist the current context storage state (encrypted) unless disabled.

        ``save_storage_state()`` takes no path and returns a path *relative to the
        robotframework-browser node wrapper's working directory*, so we resolve it
        against that directory before reading (verified 2026-07-02).
        """
        if not self.settings.persist_session:
            return
        rel = self._browser.save_storage_state()
        path = Path(rel)
        if not path.is_absolute():
            path = (_wrapper_dir() / rel).resolve()
        state = json.loads(path.read_text())
        self.session_store.save(state)
        logger.debug("session saved")

    def close(self) -> None:
        if not self._started:
            return
        try:
            self._browser.close_browser()
        finally:
            self._started = False
            temp = getattr(self, "_state_temp", None)
            if temp is not None:
                Path(temp).unlink(missing_ok=True)

    # -- accessors -------------------------------------------------------

    @property
    def browser(self) -> Any:
        """The underlying rpaframework Browser (Page Objects use this)."""
        if not self._started:
            raise RuntimeError("BrowserManager not started")
        return self._browser
