"""Output formatting across table / json / plain."""

from __future__ import annotations

import io
import json

import pytest

from odoo_sh_cli.output import Output, OutputFormat

ROWS = [
    {"name": "main", "stage": "production", "status": "running"},
    {"name": "dev", "stage": "development", "status": "stopped"},
]


def _out(fmt: OutputFormat) -> tuple[Output, io.StringIO]:
    buf = io.StringIO()
    return Output(fmt, file=buf), buf


def test_json_render_is_valid_and_complete() -> None:
    out, buf = _out(OutputFormat.json)
    out.render(ROWS)
    assert json.loads(buf.getvalue()) == ROWS


def test_plain_render_is_tab_separated() -> None:
    out, buf = _out(OutputFormat.plain)
    out.render(ROWS, columns=["name", "status"])
    lines = buf.getvalue().strip().splitlines()
    assert lines[0].split("\t") == ["main", "running"]
    assert lines[1].split("\t") == ["dev", "stopped"]


def test_table_render_contains_headers_and_values() -> None:
    out, buf = _out(OutputFormat.table)
    out.render(ROWS)
    text = buf.getvalue()
    assert "name" in text and "stage" in text
    assert "production" in text


def test_render_one_json() -> None:
    out, buf = _out(OutputFormat.json)
    out.render_one({"session": "valid"})
    assert json.loads(buf.getvalue()) == {"session": "valid"}


def test_message_structured_in_json() -> None:
    out, buf = _out(OutputFormat.json)
    out.message("hello")
    assert json.loads(buf.getvalue()) == {"message": "hello"}


@pytest.mark.parametrize("value,expected", [(True, "true"), (False, "false"), (None, "")])
def test_stringify_bool_and_none(value: object, expected: str) -> None:
    out, buf = _out(OutputFormat.plain)
    out.render([{"v": value}], columns=["v"])
    assert buf.getvalue().strip() == expected
