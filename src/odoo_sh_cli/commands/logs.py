"""`logs` command group (spec §8.5)."""

from __future__ import annotations

import typer

from ..context import RuntimeContext
from ..helpers import authed_service
from ..services.log_service import LogService

app = typer.Typer(help="Logs & monitoring.", no_args_is_help=True)


@app.command()
def show(
    ctx: typer.Context,
    branch: str = typer.Argument(..., help="Branch name."),
    lines: int = typer.Option(None, "--lines", help="Tail the last N lines."),
) -> None:
    """Print a branch's current logs."""
    rt: RuntimeContext = ctx.obj
    project = rt.settings.require_project()
    with authed_service(rt, LogService) as svc:
        entries = svc.show(project, branch, lines)
    rt.output.render([{"line": line} for line in entries], columns=["line"])


@app.command()
def monitor(
    ctx: typer.Context,
    branch: str = typer.Argument(..., help="Branch name."),
    interval: float = typer.Option(5.0, "--interval", help="Poll interval (seconds)."),
) -> None:
    """Stream new log lines until interrupted (Ctrl-C)."""
    rt: RuntimeContext = ctx.obj
    project = rt.settings.require_project()
    with authed_service(rt, LogService) as svc:
        try:
            for line in svc.monitor(project, branch, interval=interval):
                rt.output.message(line)
        except KeyboardInterrupt:
            rt.output.message("monitoring stopped")
