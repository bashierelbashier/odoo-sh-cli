"""Output formatting: table (Rich), json, and plain (grep-friendly).

Services return plain Python data (lists of dicts / dicts / scalars). The CLI
layer hands that data to :class:`Output`, which renders it in the format the
user selected with ``--output``. Keeping rendering here means commands never
build tables or serialize JSON themselves.
"""

from __future__ import annotations

import enum
import json
import sys
from collections.abc import Sequence
from typing import IO, Any

from rich.console import Console
from rich.table import Table


class OutputFormat(enum.StrEnum):
    table = "table"
    json = "json"
    plain = "plain"


Row = dict[str, Any]


class Output:
    """Renders structured data to the chosen format.

    ``plain`` output is written directly to the stream (not via Rich) so tabs
    are preserved for ``cut``/``awk``; ``table`` and ``json`` go through Rich.
    """

    def __init__(self, fmt: OutputFormat, file: IO[str] | None = None) -> None:
        self.fmt = fmt
        # Data goes to stdout so it can be piped/redirected.
        self.file = file or sys.stdout
        self.console = Console(file=self.file)

    def render(self, rows: Sequence[Row], columns: Sequence[str] | None = None) -> None:
        """Render a list of uniform records.

        ``columns`` fixes column order/subset; if omitted, keys of the first row
        are used (preserving insertion order).
        """
        rows = list(rows)
        if columns is None:
            columns = list(rows[0].keys()) if rows else []

        if self.fmt is OutputFormat.json:
            self.console.print_json(json.dumps([dict(r) for r in rows]))
        elif self.fmt is OutputFormat.plain:
            for row in rows:
                self._write_plain("\t".join(_stringify(row.get(c)) for c in columns))
        else:
            table = Table(show_header=True, header_style="bold")
            for col in columns:
                table.add_column(col)
            for row in rows:
                table.add_row(*[_stringify(row.get(c)) for c in columns])
            self.console.print(table)

    def render_one(self, obj: Row) -> None:
        """Render a single record as key/value pairs."""
        if self.fmt is OutputFormat.json:
            self.console.print_json(json.dumps(dict(obj)))
        elif self.fmt is OutputFormat.plain:
            for key, value in obj.items():
                self._write_plain(f"{key}\t{_stringify(value)}")
        else:
            table = Table(show_header=False)
            table.add_column("key", style="bold")
            table.add_column("value")
            for key, value in obj.items():
                table.add_row(str(key), _stringify(value))
            self.console.print(table)

    def message(self, text: str) -> None:
        """Emit a human-readable status line (structured object in JSON mode)."""
        if self.fmt is OutputFormat.json:
            self.console.print_json(json.dumps({"message": text}))
        elif self.fmt is OutputFormat.plain:
            self._write_plain(text)
        else:
            self.console.print(text)

    def _write_plain(self, line: str) -> None:
        """Write a raw line, bypassing Rich so tabs survive for cut/awk."""
        self.file.write(line + "\n")


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
