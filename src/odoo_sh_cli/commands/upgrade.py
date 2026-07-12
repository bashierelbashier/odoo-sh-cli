"""`upgrade` command group (spec §8.6)."""

from __future__ import annotations

import typer

from ..context import RuntimeContext
from ..helpers import authed_service, confirm, preview
from ..services.upgrade_service import UpgradeService

app = typer.Typer(help="Version upgrades.", no_args_is_help=True)


@app.command()
def status(ctx: typer.Context, branch: str = typer.Argument(..., help="Branch name.")) -> None:
    """Show current upgrade status for a branch."""
    rt: RuntimeContext = ctx.obj
    project = rt.settings.require_project()
    with authed_service(rt, UpgradeService) as svc:
        info = svc.status(project, branch)
    rt.output.render_one(info)


@app.command()
def run(
    ctx: typer.Context,
    branch: str = typer.Argument(..., help="Branch name."),
    target_version: str = typer.Option(None, "--target-version", help="Target Odoo version."),
) -> None:
    """Start a database upgrade for a branch."""
    rt: RuntimeContext = ctx.obj
    project = rt.settings.require_project()
    if preview(rt, f"run upgrade on '{branch}'"):
        return
    if not confirm(rt, f"Start an upgrade on '{branch}'?"):
        raise typer.Abort()
    with authed_service(rt, UpgradeService) as svc:
        svc.run(project, branch, target_version)
    rt.output.message(f"Upgrade started on '{branch}'.")
