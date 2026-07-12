"""`project` command group (spec §8.7)."""

from __future__ import annotations

import typer

from ..context import RuntimeContext
from ..helpers import authed_service, preview
from ..services.project_service import ProjectService

app = typer.Typer(help="Project-level settings.", no_args_is_help=True)


@app.command()
def info(ctx: typer.Context) -> None:
    """Show project overview (name, repo, version, status, license)."""
    rt: RuntimeContext = ctx.obj
    project = rt.settings.require_project()
    with authed_service(rt, ProjectService) as svc:
        data = svc.info(project)
    rt.output.render_one(data)


@app.command()
def settings(ctx: typer.Context) -> None:
    """Read current project settings."""
    rt: RuntimeContext = ctx.obj
    project = rt.settings.require_project()
    with authed_service(rt, ProjectService) as svc:
        data = svc.settings(project)
    rt.output.render_one(data)


@app.command(name="set-commit-status-token")
def set_commit_status_token(
    ctx: typer.Context,
    token: str = typer.Argument(..., help="Commit status token (treated as a secret)."),
) -> None:
    """Set/rotate the GitHub commit status token."""
    rt: RuntimeContext = ctx.obj
    project = rt.settings.require_project()
    if preview(rt, "set commit status token"):
        return
    with authed_service(rt, ProjectService) as svc:
        svc.set_commit_status_token(project, token)
    rt.output.message("Commit status token updated.")
