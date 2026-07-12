"""Logging configuration with a non-negotiable secret-scrubbing filter.

Secrets (password, TOTP secret, tokens, cookie values) must never reach logs,
stderr, screenshots, or traces (spec §5.5). We register the concrete secret
values with :class:`SecretScrubber` as they become known, and the filter
redacts them from every log record — regardless of which module logged them.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from rich.logging import RichHandler

REDACTION = "***REDACTED***"


class SecretScrubber(logging.Filter):
    """Removes registered secret values from log messages and args.

    The set of secrets is class-level so that any code (including third-party
    libraries routed through the root logger) is scrubbed once we know a value.
    """

    _secrets: ClassVar[set[str]] = set()

    @classmethod
    def register(cls, *values: str | None) -> None:
        """Register secret values to redact. ``None``/empty values are ignored."""
        for value in values:
            if value:
                cls._secrets.add(value)

    @classmethod
    def scrub(cls, text: str) -> str:
        for secret in cls._secrets:
            if secret and secret in text:
                text = text.replace(secret, REDACTION)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.scrub(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._scrub_arg(v) for k, v in record.args.items()}
            else:
                record.args = tuple(self._scrub_arg(a) for a in record.args)
        return True

    @staticmethod
    def _scrub_arg(arg: object) -> object:
        return SecretScrubber.scrub(arg) if isinstance(arg, str) else arg


def configure_logging(verbosity: int) -> None:
    """Configure root logging from a ``-v`` count (0=warning, 1=info, 2=debug)."""
    level = {0: logging.WARNING, 1: logging.INFO}.get(verbosity, logging.DEBUG)
    handler = RichHandler(rich_tracebacks=verbosity >= 2, show_path=verbosity >= 2)
    handler.addFilter(SecretScrubber())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
