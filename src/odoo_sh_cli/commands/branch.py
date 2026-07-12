"""`branch` command group (spec §8.2)."""

from __future__ import annotations

import typer

from ..context import RuntimeContext
from ..helpers import authed_service, confirm, preview
from ..services.branch_service import BranchService

app = typer.Typer(help="Branch operations.", no_args_is_help=True)


@app.command(name="list")
def list_branches(
    ctx: typer.Context,
    stage: str = typer.Option(None, "--stage", help="Filter: production|staging|development."),
) -> None:
    """List branches (name, stage, url)."""
    rt: RuntimeContext = ctx.obj
    project = rt.settings.require_project()
    with authed_service(rt, BranchService) as svc:
        rows = svc.list_branches(project, stage)
    rt.output.render(rows, columns=["name", "stage", "url"])


@app.command()
def history(
    ctx: typer.Context,
    branch: str = typer.Argument(..., help="Branch name."),
    limit: int = typer.Option(20, "--limit", help="Max entries."),
) -> None:
    """Show recent builds/events for a branch."""
    rt: RuntimeContext = ctx.obj
    project = rt.settings.require_project()
    with authed_service(rt, BranchService) as svc:
        rows = svc.history(project, branch, limit)
    rt.output.render(rows, columns=["event"])


@app.command()
def rebuild(
    ctx: typer.Context,
    branch: str = typer.Argument(..., help="Branch to rebuild."),
) -> None:
    """Trigger a rebuild of the branch's build."""
    rt: RuntimeContext = ctx.obj
    project = rt.settings.require_project()
    if preview(rt, f"rebuild branch '{branch}'"):
        return
    if not confirm(rt, f"Rebuild branch '{branch}'?"):
        raise typer.Abort()
    with authed_service(rt, BranchService) as svc:
        svc.rebuild(project, branch)
    rt.output.message(f"Rebuild triggered for '{branch}'.")


@app.command()
def delete(
    ctx: typer.Context,
    branch: str = typer.Argument(..., help="Branch to delete."),
) -> None:
    """Delete a branch and its build. DESTRUCTIVE."""
    rt: RuntimeContext = ctx.obj
    project = rt.settings.require_project()
    if preview(rt, f"delete branch '{branch}'"):
        return
    if not confirm(rt, f"Permanently delete branch '{branch}'?"):
        raise typer.Abort()
    with authed_service(rt, BranchService) as svc:
        svc.delete(project, branch)
    rt.output.message(f"Deleted branch '{branch}'.")


@app.command()
def settings(
    ctx: typer.Context,
    branch: str = typer.Argument(..., help="Branch name."),
    set_: list[str] = typer.Option(
        None, "--set", help="key=value (repeatable). Omit to just read settings."
    ),
) -> None:
    """Read or update branch settings."""
    rt: RuntimeContext = ctx.obj
    project = rt.settings.require_project()
    pairs = _parse_pairs(set_)
    if pairs and preview(rt, f"set {pairs} on branch '{branch}'"):
        return
    with authed_service(rt, BranchService) as svc:
        result = (
            svc.set_settings(project, branch, pairs)
            if pairs
            else svc.read_settings(project, branch)
        )
    rt.output.render_one(result)


@app.command(name="connect-info")
def connect_info(
    ctx: typer.Context,
    branch: str = typer.Argument(..., help="Branch name."),
) -> None:
    """Show connection details (Git remote / SSH) for a branch."""
    rt: RuntimeContext = ctx.obj
    project = rt.settings.require_project()
    with authed_service(rt, BranchService) as svc:
        info = svc.connection_info(project, branch)
    rt.output.render_one(info)


def _parse_pairs(items: list[str] | None) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for item in items or []:
        if "=" not in item:
            raise typer.BadParameter(f"--set expects key=value, got '{item}'")
        key, value = item.split("=", 1)
        pairs[key.strip()] = value.strip()
    return pairs
