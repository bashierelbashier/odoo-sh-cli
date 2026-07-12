"""Confirmation / dry-run / polling / retry helpers (spec §6.4, §10)."""

from __future__ import annotations

import io

import pytest

from odoo_sh_cli.config import Settings
from odoo_sh_cli.context import RuntimeContext
from odoo_sh_cli.errors import UITimeoutError
from odoo_sh_cli.helpers import confirm, poll, preview, retry
from odoo_sh_cli.output import Output, OutputFormat


def _rt(*, dry_run: bool = False, yes: bool = False) -> tuple[RuntimeContext, io.StringIO]:
    buf = io.StringIO()
    rt = RuntimeContext(
        settings=Settings(),
        output=Output(OutputFormat.plain, file=buf),
        dry_run=dry_run,
        yes=yes,
    )
    return rt, buf


def test_confirm_yes_flag_skips_prompt() -> None:
    rt, _ = _rt(yes=True)
    assert confirm(rt, "delete?") is True


def test_confirm_dry_run_never_proceeds() -> None:
    rt, _ = _rt(dry_run=True)
    assert confirm(rt, "delete?") is False


def test_preview_announces_and_stops_in_dry_run() -> None:
    rt, buf = _rt(dry_run=True)
    assert preview(rt, "rebuild branch main") is True
    assert "would rebuild branch main" in buf.getvalue()


def test_preview_noop_when_not_dry_run() -> None:
    rt, buf = _rt()
    assert preview(rt, "rebuild") is False
    assert buf.getvalue() == ""


def test_poll_returns_when_done() -> None:
    states = iter(["building", "building", "done"])
    slept: list[float] = []
    result = poll(
        lambda: next(states),
        lambda s: s == "done",
        timeout=100,
        interval=1,
        sleep=slept.append,
    )
    assert result == "done"
    assert slept == [1, 1]  # slept between the three fetches


def test_poll_times_out() -> None:
    with pytest.raises(UITimeoutError):
        poll(lambda: "building", lambda s: s == "done", timeout=0, sleep=lambda _: None)


def test_retry_succeeds_after_transient_failures() -> None:
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise UITimeoutError("slow")
        return "ok"

    assert retry(flaky, attempts=3, sleep=lambda _: None) == "ok"
    assert calls["n"] == 3


def test_retry_reraises_after_exhausting_attempts() -> None:
    def always_fail() -> str:
        raise UITimeoutError("nope")

    with pytest.raises(UITimeoutError):
        retry(always_fail, attempts=2, sleep=lambda _: None)
