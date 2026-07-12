"""Runtime context wired once in the root callback and injected into commands.

Typer stores this on ``ctx.obj``. It holds the resolved :class:`Settings`, the
selected :class:`Output`, and the mutating-command flags (``dry_run``/``yes``),
plus lazy factories for the browser and services so read-only help/usage never
launches a browser.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .config import ConfigManager, CredentialStore, Settings
from .output import Output

if TYPE_CHECKING:
    from .automation.browser_manager import BrowserManager


@dataclass
class RuntimeContext:
    settings: Settings
    output: Output
    dry_run: bool = False
    yes: bool = False
    trace: bool = False
    config_manager: ConfigManager = field(default_factory=ConfigManager)
    credentials: CredentialStore = field(default_factory=CredentialStore)

    @contextmanager
    def browser(self) -> Iterator[BrowserManager]:
        """Yield a started :class:`BrowserManager`, closing it on exit.

        Imported lazily to keep CLI startup (and unit tests) free of Playwright.
        """
        from .automation.browser_manager import BrowserManager

        manager = BrowserManager(self.settings)
        try:
            manager.start()
            yield manager
        finally:
            manager.close()
