"""Secret-scrubbing log filter (spec §5.5, §11)."""

from __future__ import annotations

import logging

from odoo_sh_cli.logging_setup import REDACTION, SecretScrubber


def _record(msg: str, *args: object) -> logging.LogRecord:
    return logging.LogRecord("t", logging.INFO, __file__, 1, msg, args, None)


def test_scrub_replaces_registered_secret() -> None:
    SecretScrubber.register("hunter2")
    assert SecretScrubber.scrub("password is hunter2") == f"password is {REDACTION}"


def test_filter_scrubs_message_and_args() -> None:
    SecretScrubber.register("topsecret")
    scrubber = SecretScrubber()
    record = _record("value=%s", "topsecret")
    scrubber.filter(record)
    assert record.args == (REDACTION,)


def test_register_ignores_empty_values() -> None:
    before = set(SecretScrubber._secrets)
    SecretScrubber.register(None, "")
    assert SecretScrubber._secrets == before


def test_scrub_leaves_clean_text_untouched() -> None:
    assert SecretScrubber.scrub("nothing sensitive here") == "nothing sensitive here"
