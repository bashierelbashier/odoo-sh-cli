"""`auth` command group: setup, login, status, logout (spec §8.1)."""

from __future__ import annotations

import typer

from ..context import RuntimeContext
from ..errors import ExitCode
from ..services.auth_service import AuthService
from ..session import SessionStore

app = typer.Typer(help="Authentication & session management.", no_args_is_help=True)


@app.command()
def setup(ctx: typer.Context) -> None:
    """Prompt for and store GitHub credentials in the OS keyring (no browser)."""
    rt: RuntimeContext = ctx.obj
    store = rt.credentials

    username = typer.prompt("GitHub username")
    password = typer.prompt("GitHub password", hide_input=True)
    totp_secret = typer.prompt(
        "GitHub TOTP secret (base32, blank to skip)", default="", hide_input=True
    )

    store.set("github_username", username)
    store.set("github_password", password)
    if totp_secret:
        store.set("github_totp_secret", totp_secret)

    rt.output.message(f"Stored credentials for {username} (secrets not echoed).")


@app.command()
def login(ctx: typer.Context) -> None:
    """Run the full GitHub -> Odoo.sh login flow and persist the session."""
    rt: RuntimeContext = ctx.obj
    with rt.browser() as browser:
        service = AuthService(browser, credentials=rt.credentials)
        username = service.login()
    rt.output.message(f"Authenticated as {username}")


@app.command()
def status(ctx: typer.Context) -> None:
    """Load the saved session and verify it. Exit 0 if valid, 3 if not."""
    rt: RuntimeContext = ctx.obj
    with rt.browser() as browser:
        service = AuthService(browser, credentials=rt.credentials)
        valid = service.status()
    rt.output.render_one({"session": "valid" if valid else "invalid"})
    if not valid:
        raise typer.Exit(ExitCode.AUTH)


@app.command()
def logout(ctx: typer.Context) -> None:
    """Delete the persisted session file (no browser)."""
    rt: RuntimeContext = ctx.obj
    removed = SessionStore().clear()
    rt.output.message("Session cleared." if removed else "No session to clear.")
