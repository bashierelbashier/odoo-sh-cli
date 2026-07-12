"""Typer application: entry point, global options, and error-to-exit mapping."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from . import __version__
from .commands import auth as auth_commands
from .commands import backup as backup_commands
from .commands import branch as branch_commands
from .commands import domain as domain_commands
from .commands import logs as logs_commands
from .commands import project as project_commands
from .commands import upgrade as upgrade_commands
from .config import ConfigManager
from .context import RuntimeContext
from .errors import ExitCode, OdooShError
from .logging_setup import configure_logging
from .output import Output, OutputFormat

app = typer.Typer(
    name="odoo-sh",
    help="RPA CLI to manage Odoo.sh projects by driving the web UI.",
    no_args_is_help=True,
    add_completion=False,
)

app.add_typer(auth_commands.app, name="auth")
app.add_typer(branch_commands.app, name="branch")
app.add_typer(backup_commands.app, name="backup")
app.add_typer(domain_commands.app, name="domain")
app.add_typer(logs_commands.app, name="logs")
app.add_typer(upgrade_commands.app, name="upgrade")
app.add_typer(project_commands.app, name="project")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    project: str | None = typer.Option(
        None, "--project", "-p", help="Odoo.sh project name to operate on."
    ),
    profile: str = typer.Option("default", "--profile", help="Named config profile."),
    config: Path | None = typer.Option(
        None, "--config", help="Config file path (default ~/.config/odoo-sh-cli/config.toml)."
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.table, "--output", "-o", help="Output format."
    ),
    headless: bool = typer.Option(True, "--headless/--no-headless", help="Run browser headless."),
    timeout: int | None = typer.Option(None, "--timeout", help="Per-action wait (seconds)."),
    persist_session: bool = typer.Option(
        True, "--persist-session/--no-persist-session", help="Persist the browser session."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview mutating actions only."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompts."),
    trace: bool = typer.Option(False, "--trace", help="Keep the Playwright trace file."),
    verbose: int = typer.Option(0, "--verbose", "-v", count=True, help="-v info, -vv debug."),
    version: bool | None = typer.Option(
        None, "--version", callback=_version_callback, is_eager=True, help="Print version and exit."
    ),
) -> None:
    """Resolve configuration and build the runtime context for subcommands."""
    configure_logging(verbose)

    config_manager = ConfigManager(config)
    settings = config_manager.resolve(
        profile=profile,
        project=project,
        headless=headless,
        timeout=timeout,
        persist_session=persist_session,
    )
    ctx.obj = RuntimeContext(
        settings=settings,
        output=Output(output),
        dry_run=dry_run,
        yes=yes,
        trace=trace,
        config_manager=config_manager,
    )


def run() -> None:
    """Console-script wrapper that maps :class:`OdooShError` to exit codes."""
    try:
        app()
    except OdooShError as exc:
        print(f"error: {exc.message}", file=sys.stderr)
        raise SystemExit(exc.exit_code) from exc
    except KeyboardInterrupt:
        print("aborted", file=sys.stderr)
        raise SystemExit(ExitCode.GENERIC) from None


if __name__ == "__main__":
    run()
