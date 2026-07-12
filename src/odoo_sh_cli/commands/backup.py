"""`backup` command group (spec §8.3)."""

from __future__ import annotations

from pathlib import Path

import typer

from ..context import RuntimeContext
from ..helpers import authed_service, confirm, preview
from ..services.backup_service import BackupService

app = typer.Typer(help="Backups.", no_args_is_help=True)


@app.command(name="list")
def list_backups(
    ctx: typer.Context, branch: str = typer.Argument(..., help="Branch name.")
) -> None:
    """List available backups for a branch."""
    rt: RuntimeContext = ctx.obj
    project = rt.settings.require_project()
    with authed_service(rt, BackupService) as svc:
        rows = svc.list_backups(project, branch)
    rt.output.render(rows)


@app.command()
def create(
    ctx: typer.Context,
    branch: str = typer.Argument(..., help="Branch name."),
    comment: str = typer.Option(None, "--comment", help="Backup comment."),
) -> None:
    """Trigger a manual backup."""
    rt: RuntimeContext = ctx.obj
    project = rt.settings.require_project()
    if preview(rt, f"create backup of '{branch}'"):
        return
    with authed_service(rt, BackupService) as svc:
        svc.create(project, branch, comment)
    rt.output.message(f"Backup requested for '{branch}'.")


@app.command()
def download(
    ctx: typer.Context,
    branch: str = typer.Argument(..., help="Branch name."),
    backup_id: str = typer.Option(None, "--backup-id", help="Backup id (default: latest)."),
    dest: Path = typer.Option(Path.cwd(), "--dest", help="Destination directory or file."),
) -> None:
    """Download a backup artifact."""
    rt: RuntimeContext = ctx.obj
    project = rt.settings.require_project()
    if preview(rt, f"download backup of '{branch}' to {dest}"):
        return
    with authed_service(rt, BackupService) as svc:
        saved = svc.download(project, branch, dest, backup_id)
    rt.output.render_one({"saved": str(saved)})


@app.command()
def restore(
    ctx: typer.Context,
    branch: str = typer.Argument(..., help="Target branch."),
    from_: str = typer.Option(..., "--from", help="Backup id or local file path."),
) -> None:
    """Restore a backup onto a branch. DESTRUCTIVE — overwrites branch data."""
    rt: RuntimeContext = ctx.obj
    project = rt.settings.require_project()
    if preview(rt, f"restore '{from_}' onto '{branch}' (overwrites data)"):
        return
    if not confirm(rt, f"Overwrite branch '{branch}' with backup '{from_}'?"):
        raise typer.Abort()
    with authed_service(rt, BackupService) as svc:
        svc.restore(project, branch, from_)
    rt.output.message(f"Restore started on '{branch}' from '{from_}'.")
