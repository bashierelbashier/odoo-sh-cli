"""Reusable command helpers: confirmation, dry-run, polling, retry/backoff.

These keep the cross-cutting "definition of done" (spec §6.4, §10) in one place
so every mutating/long-running command behaves consistently.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TypeVar

import typer

from .context import RuntimeContext
from .errors import UITimeoutError

logger = logging.getLogger(__name__)

T = TypeVar("T")


@contextmanager
def authed_service(rt: RuntimeContext, service_cls: Callable[..., T]) -> Iterator[T]:
    """Yield ``service_cls(browser)`` with a verified Odoo.sh session.

    Opens the browser, ensures a valid session (reusing the encrypted one or
    logging in once), then constructs the service. Closes the browser on exit.
    """
    from .services.auth_service import AuthService

    with rt.browser() as browser:
        AuthService(browser, credentials=rt.credentials).ensure_session()
        yield service_cls(browser)


def confirm(rt: RuntimeContext, prompt: str) -> bool:
    """Return True if the action should proceed.

    ``--yes`` skips the prompt; ``--dry-run`` never proceeds (caller should have
    already printed the preview via :func:`preview`).
    """
    if rt.dry_run:
        return False
    if rt.yes:
        return True
    return typer.confirm(prompt)


def preview(rt: RuntimeContext, action: str) -> bool:
    """If dry-run, announce the action and return True (caller should stop)."""
    if rt.dry_run:
        rt.output.message(f"[dry-run] would {action}")
        return True
    return False


def poll(
    fetch: Callable[[], T],
    is_done: Callable[[T], bool],
    *,
    timeout: float,
    interval: float = 5.0,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call ``fetch`` until ``is_done`` is true or ``timeout`` (seconds) elapses.

    ``sleep`` is injectable so tests don't wait in real time. Returns the last
    fetched value on success; raises :class:`UITimeoutError` on timeout.
    """
    deadline = time.monotonic() + timeout
    while True:
        value = fetch()
        if is_done(value):
            return value
        if time.monotonic() >= deadline:
            raise UITimeoutError(f"Operation did not complete within {timeout:.0f}s.")
        sleep(interval)


def retry(
    func: Callable[[], T],
    *,
    attempts: int = 3,
    backoff: float = 1.0,
    exceptions: tuple[type[Exception], ...] = (UITimeoutError,),
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Run ``func`` with bounded retries and exponential backoff.

    For transient *read* failures only — never wrap destructive actions (§10).
    Re-raises the last exception after exhausting attempts.
    """
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except exceptions as exc:
            last = exc
            if attempt == attempts:
                break
            wait = backoff * (2 ** (attempt - 1))
            logger.debug(
                "attempt %d/%d failed (%s); retrying in %.1fs", attempt, attempts, exc, wait
            )
            sleep(wait)
    assert last is not None
    raise last
