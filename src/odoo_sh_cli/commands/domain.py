"""`domain` command group (spec §8.4)."""

from __future__ import annotations

import typer

from ..context import RuntimeContext
from ..helpers import authed_service, confirm, preview
from ..services.domain_service import DomainService

app = typer.Typer(help="Instance custom domains.", no_args_is_help=True)


@app.command(name="list")
def list_domains(
    ctx: typer.Context, branch: str = typer.Argument(..., help="Branch name.")
) -> None:
    """List configured domains for a branch's instance."""
    rt: RuntimeContext = ctx.obj
    project = rt.settings.require_project()
    with authed_service(rt, DomainService) as svc:
        rows = svc.list_domains(project, branch)
    rt.output.render(rows, columns=["domain"])


@app.command(name="set")
def set_domain(
    ctx: typer.Context,
    branch: str = typer.Argument(..., help="Branch name."),
    domain: str = typer.Argument(..., help="Domain to add/configure."),
) -> None:
    """Add or configure a custom domain."""
    rt: RuntimeContext = ctx.obj
    project = rt.settings.require_project()
    if preview(rt, f"set domain '{domain}' on '{branch}'"):
        return
    with authed_service(rt, DomainService) as svc:
        svc.set(project, branch, domain)
    rt.output.message(f"Domain '{domain}' set on '{branch}'.")


@app.command()
def remove(
    ctx: typer.Context,
    branch: str = typer.Argument(..., help="Branch name."),
    domain: str = typer.Argument(..., help="Domain to remove."),
) -> None:
    """Remove a configured domain."""
    rt: RuntimeContext = ctx.obj
    project = rt.settings.require_project()
    if preview(rt, f"remove domain '{domain}' from '{branch}'"):
        return
    if not confirm(rt, f"Remove domain '{domain}' from '{branch}'?"):
        raise typer.Abort()
    with authed_service(rt, DomainService) as svc:
        svc.remove(project, branch, domain)
    rt.output.message(f"Domain '{domain}' removed from '{branch}'.")
