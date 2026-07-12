# odoo-sh-cli

A command-line tool to manage [Odoo.sh](https://www.odoo.sh) projects.

Odoo.sh has no public management API, so this tool drives the web UI with Robot
Framework's RPA capabilities (Playwright backend). It logs in with a GitHub
account (Odoo.sh uses "Log in with GitHub"), then runs operations: list and
rebuild branches, manage backups, set domains, read and monitor logs, run
upgrades, and edit branch/project settings.

---

## Install

Requires Python 3.11+.

**One-liner (recommended)** — installs [`uv`](https://docs.astral.sh/uv/) if
needed, then all dependencies, the automation browser, and dev hooks:

```bash
./setup.sh              # or: ./setup.sh --no-dev  for a runtime-only install
uv run odoo-sh --help
```

**With uv, manually:**

```bash
uv sync                 # install the package and dependencies
uv run rfbrowser init   # one-time: download the Playwright browser (required)
uv run odoo-sh --help
```

**With pip (no uv):**

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
rfbrowser init
odoo-sh --help
```

`rfbrowser init` downloads a Chromium build used for automation. On a headless
Linux box you may also need system libraries (`sudo npx playwright install-deps`
or `apt-get install libavif16 libwoff1`); Chromium usually runs without them.

---

## Providing your GitHub username and password

Odoo.sh authentication goes through GitHub. You give the tool a GitHub
**username** and **password** (and, if the account has 2FA, a TOTP secret). Use a
**dedicated GitHub service account** — not a personal one — that has been added
as a collaborator on both the GitHub repository and the Odoo.sh project.

There are three ways to supply the credentials. Precedence, highest first:
**command-line flag → environment variable → config file → built-in default.**

### Option 1 — interactive setup (recommended for a workstation)

Stores the credentials in your operating system's keyring (encrypted; never in
plaintext, never in the repo):

```bash
uv run odoo-sh auth setup
# GitHub username: my-bot-account
# GitHub password: ********           (hidden; not echoed)
# GitHub TOTP secret (base32, blank to skip): ******   (only if the account uses 2FA)
```

Then log in once (this opens a browser session that is saved and reused):

```bash
uv run odoo-sh auth login
uv run odoo-sh auth status     # -> session: valid
```

If GitHub shows a CAPTCHA or device-verification prompt, run the login with a
visible browser to solve it once: `uv run odoo-sh auth login --no-headless`.

### Option 2 — environment variables (recommended for CI / automation)

```bash
export ODOO_SH_GITHUB_USERNAME="my-bot-account"
export ODOO_SH_GITHUB_PASSWORD="the-password"
export ODOO_SH_GITHUB_TOTP_SECRET="BASE32SECRET"   # optional, only if 2FA is on
export ODOO_SH_PROJECT="my-project"

uv run odoo-sh auth login
uv run odoo-sh branch list
```

Environment variables override the keyring, so they're ideal for pipelines. The
password and TOTP secret are scrubbed from all logs and error output.

### Option 3 — config file

`~/.config/odoo-sh-cli/config.toml` holds non-secret settings and profiles (for
managing multiple projects/accounts). **Do not put passwords here** — use the
keyring or env vars for secrets.

```toml
default_project = "my-project"

[profiles.default]
project = "my-project"
headless = true
timeout = 60

[profiles.staging-admin]
project = "my-project-staging"
```

Select a profile with `--profile staging-admin`.

### How the login works

```
odoo-sh  →  github.com/login (your username + password [+ TOTP])  →  Odoo.sh dashboard
```

The first successful login saves an **encrypted browser session** to
`~/.config/odoo-sh-cli/session.enc` (Fernet-encrypted, `0600`, key in the OS
keyring). Later commands reuse that session, so you are not logged in on every
call. Use `--no-persist-session` on shared machines to avoid saving it.

---

## Global options

| Option | Meaning |
|--------|---------|
| `--project, -p` | Odoo.sh project name (or `ODOO_SH_PROJECT`, or config). |
| `--profile` | Config profile to use (default `default`). |
| `--config` | Config file path. |
| `--output, -o` | `table` (default), `json`, or `plain` (tab-separated, grep-friendly). |
| `--headless / --no-headless` | Hide or show the browser. |
| `--timeout` | Per-action browser wait, seconds (default 60). |
| `--dry-run` | Preview mutating actions without performing them. |
| `--yes, -y` | Skip confirmation prompts for destructive actions. |
| `--persist-session / --no-persist-session` | Save/reuse the browser session. |
| `--verbose, -v` | `-v` info, `-vv` debug logging. |
| `--version` | Print version and exit. |

---

## Commands

Every read command supports `-o table|json|plain`. Destructive commands
(`branch delete`, `backup restore`) prompt for confirmation unless `--yes`, and
honor `--dry-run`.

### auth

```bash
odoo-sh auth setup            # store GitHub credentials in the keyring
odoo-sh auth login            # log in and persist the session
odoo-sh auth status           # check whether the saved session is valid
odoo-sh auth logout           # delete the saved session
```

### branch

```bash
odoo-sh branch list [--stage production|staging|development]
odoo-sh branch history <branch> [--limit N]
odoo-sh branch rebuild <branch> [--dry-run] [--yes]
odoo-sh branch delete <branch>  [--dry-run] [--yes]          # DESTRUCTIVE
odoo-sh branch settings <branch> [--set key=value ...]       # read, or set
odoo-sh branch connect-info <branch>                         # Git/SSH details
```

### backup

```bash
odoo-sh backup list <branch>
odoo-sh backup create <branch> [--comment "text"]
odoo-sh backup download <branch> [--backup-id ID] [--dest PATH]
odoo-sh backup restore <branch> --from <backup-id|file> [--yes]   # DESTRUCTIVE
```

### domain

```bash
odoo-sh domain list <branch>
odoo-sh domain set <branch> <domain>
odoo-sh domain remove <branch> <domain> [--yes]
```

### logs

```bash
odoo-sh logs show <branch> [--lines N]
odoo-sh logs monitor <branch> [--interval SECONDS]   # stream until Ctrl-C
```

### upgrade

```bash
odoo-sh upgrade status <branch>
odoo-sh upgrade run <branch> [--target-version X.Y] [--yes]
```

### project

```bash
odoo-sh project info                              # name, repo, version, status
odoo-sh project settings                          # read project settings
odoo-sh project set-commit-status-token <token>   # token treated as a secret
```

---

## Output & exit codes

- `table` — human-readable; `json` — for scripting; `plain` — tab-separated lines.
- Exit codes: `0` success, `1` generic error, `2` usage error, `3` authentication
  error, `4` operation failed on Odoo.sh, `5` timeout / element not found.

---

## Maturity of commands

- **Read-only commands** (`auth status`, `branch list`/`history`,
  `project info`, `logs show`, `backup list`) are verified end-to-end against a
  live Odoo.sh project.
- **Mutating / destructive commands** (rebuild, delete, backup create/download/
  restore, domain set/remove, upgrade run, settings writes) are fully wired and
  guarded by `--dry-run`/`--yes`/confirmation, but their underlying UI actions
  are **best-effort and not yet exercised against real production data**. Use
  `--dry-run` first, and treat them as beta until verified on a throwaway branch.

---

## Development

```bash
./setup.sh          # bootstrap: uv, deps, browser, pre-commit hooks
make check          # lint + type-check + tests + format check
make test           # unit tests only
pre-commit run --all-files
```

`make help` lists all targets. Pre-commit runs ruff + mypy on commit and pytest
on push. See [CONTRIBUTING.md](./CONTRIBUTING.md) for the layered architecture
rules (selectors live only in `automation/pages/`).

The dependency source of truth is `pyproject.toml`; `requirements.txt` /
`requirements-dev.txt` are provided for pip users.

## Security & compliance

- Passwords, TOTP secrets, and tokens are never logged, printed, or written to
  the repo; they're scrubbed from logs and Playwright output.
- The session file and any temp files are `0600` under your config dir.
- Automating GitHub login may be subject to GitHub's Terms of Service and
  anti-automation defenses (CAPTCHA, device verification). The tool minimizes
  logins by reusing the encrypted session and surfaces a clear error if a
  challenge it cannot solve appears. Confirm automated access is permitted for
  your Odoo.sh subscription before using this in production.
