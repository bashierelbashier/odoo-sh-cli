# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status: functional (read-only verified live; mutating commands beta)

All command groups exist and are wired: `auth`, `branch`, `backup`, `domain`, `logs`,
`upgrade`, `project`. Read-only commands are verified end-to-end against a live Odoo.sh
project; mutating/destructive commands are implemented and guarded (`--dry-run`/`--yes`/
confirm) but their UI action selectors are best-effort and not yet exercised against real
data (marked `[VERIFY-ACTION]` in the page objects).

Architecture (layered, spec §4): `commands/` (Typer) → `services/` (domain ops) →
`automation/pages/` (Page Objects — the ONLY place with selectors/URLs) → cross-cutting
`config`/`session`/`output`/`errors`/`logging_setup`/`helpers`. Odoo.sh panels are reached by
verified URL routing: `/project/<p>/branches/<b>/{history,monitor,logs,backups,upgrade,tools,
settings}`, plus `/project/<p>/{settings,status,logs}` and `/project/<p>/builds/<b>`.

### Commands

- Install deps: `uv sync`
- Install browsers (once, required for RPA): `uv run rfbrowser init`
- Run the CLI: `uv run odoo-sh --help`
- Lint: `uv run ruff check src tests`
- Format: `uv run ruff format src tests` (add `--check` in CI)
- Types: `uv run mypy`
- Unit tests: `uv run pytest -q`

CI (`.github/workflows/ci.yml`) runs ruff + mypy + pytest on every push. The Robot Framework
e2e suite under `e2e/` is opt-in and needs real credentials + a disposable test project; it is
not run in normal CI.

### Progress vs. plan.md

- **Phase 0 (skeleton/tooling):** done.
- **Phase 1 (auth code) — GATE CLEARED (2026-07-02):** live headless GitHub→Odoo.sh login
  verified end-to-end with a real service account via the CLI (`auth login` → `auth status`
  reuses the encrypted session, no re-login). Verified facts baked into the code:
    - Navigating to `https://www.odoo.sh/project` while logged out redirects **straight to
      GitHub OAuth** — there is no "Log in with GitHub" button to click.
    - GitHub login: `#login_field`, `#password`, submit `input.js-sign-in-button`.
    - The test account has **no 2FA** and is **pre-authorized** (no OAuth "Authorize" screen);
      that handling is kept defensively but doesn't fire.
    - Logged-in marker: on an `odoo.sh` URL with the `a[href='/web/login']` link absent.
  - rpaframework/robotframework-browser gotchas (already handled in code): `rfbrowser init` is
    required to install browsers; `wait_for_elements_state` needs the `ElementState` enum +
    `timedelta` (not strings) when called from Python; `save_storage_state()` takes no path and
    returns one **relative to the node wrapper dir** (`Browser/wrapper/`).
- **Phase 2 (plumbing):** done (Output formatter, exception/exit-code mapping, confirm/dry-run,
  poll/`--wait`, retry/backoff, RuntimeContext injection).
- **Phases 3–8 (feature commands):** all groups implemented and unit-tested with the service
  layer faked. Read-only commands verified live; mutating commands' `[VERIFY-ACTION]` selectors
  still need live verification on a throwaway branch (do NOT test destructive actions on the
  demo project's production branch).

Live test account & how to run commands against it: see the `odoo-sh-test-account` memory.
Read-only live check: `ODOO_SH_GITHUB_USERNAME=… ODOO_SH_GITHUB_PASSWORD=… ODOO_SH_PROJECT=…
uv run odoo-sh branch list`.

## What this is

An RPA CLI tool to manage Odoo.sh projects. It authenticates a GitHub user, uses that identity to log into odoo.sh (which has no public API), and drives the odoo.sh web UI to run operations — rebuild a branch, manage backups, set domains, monitor logs, run upgrades, edit branch/project settings, etc.

Full intent and command list: @specification.md

## Key architectural constraints

- **RPA, not an API.** odoo.sh is driven via browser automation with Robot Framework's RPA capabilities — expect Python. Operations are UI flows, so they're slower and more brittle than API calls; build in explicit waits and verification, not fixed sleeps.
- **Auth chain: GitHub → odoo.sh.** Login goes through github.com, then odoo.sh's "Log in with GitHub". Credentials/tokens are secrets — never hard-code or commit them; load from env or a config file that's gitignored.
