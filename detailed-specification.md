# Odoo.sh CLI — Detailed Specification

> **Audience:** This document is written to be implementable by a junior developer or a
> less-capable AI model. It spells out concepts, decisions, and step-by-step behavior
> explicitly. When something is an assumption that must be validated against the real
> Odoo.sh UI, it is marked **[VERIFY]**.

---

## 1. Overview

`odoo-sh-cli` is a command-line tool that automates management of
[Odoo.sh](https://www.odoo.sh) projects. Odoo.sh is Odoo's cloud hosting platform (a
PaaS). It has a rich web UI but **no official public management API**. Therefore this tool
drives the Odoo.sh web interface with **RPA (Robotic Process Automation)** — it logs in and
clicks/reads the web pages like a human would, but scripted.

Authentication is done through a **GitHub account**: the tool logs into `github.com` as a
dedicated service user, then uses "Log in with GitHub" on Odoo.sh.

### 1.1 Goals

- Provide a scriptable CLI for common Odoo.sh operations (rebuild, backups, domains, logs,
  upgrades, settings).
- Be usable both interactively (a developer at a terminal) and in CI/automation
  (non-interactive, credentials from environment).
- Be resilient to the slowness and flakiness inherent to browser automation.
- Keep the automation layer isolated so that when the Odoo.sh UI changes, only a small,
  well-defined part of the code needs updating.

### 1.2 Non-goals

- Managing Odoo *inside* an instance (e.g., installing Odoo apps, editing records). This
  tool manages the **platform**, not the application data.
- Replacing `git`. Code changes still flow through GitHub as normal.
- Supporting non-GitHub authentication (e.g., raw Odoo accounts) in v1. **[VERIFY]** whether
  the target projects use GitHub login exclusively.

---

## 2. Terminology (Odoo.sh concepts)

Understand these before writing any automation. **[VERIFY]** all against a live project.

| Term | Meaning |
|------|---------|
| **Project** | A single Odoo.sh subscription, linked to one Git repository. Identified by a project name in the URL: `https://www.odoo.sh/project/<project-name>`. |
| **Branch** | Corresponds to a Git branch. Each branch runs an Odoo instance (a "build"). |
| **Stage** | Branches are grouped into stages: **Production**, **Staging**, **Development**. Production has exactly one branch; staging/development can have many. |
| **Build** | A running (or historical) deployment of a branch. Rebuilding creates a new build. |
| **Backup** | A snapshot (database + filestore) of a branch's instance. Odoo.sh keeps automatic daily backups and allows manual ones. |
| **Upgrade** | Migrating an instance's database to a newer Odoo version. |
| **Commit status token** | A token Odoo.sh uses to report build status back to GitHub commits. A project-level setting. |

---

## 3. Technology stack

| Concern | Choice | Rationale |
|--------|--------|-----------|
| Language | **Python 3.11+** | Required by Robot Framework / rpaframework; spec mandates Robot Framework RPA. |
| RPA / browser automation | **rpaframework** (`RPA.Browser.Playwright`) | Satisfies "use Robot Framework's RPA capabilities". Playwright backend is faster and more reliable than Selenium, with auto-waiting. |
| CLI framework | **Typer** (built on Click) + **Rich** | Declarative subcommands, typed args, good help output, colored/table output via Rich. |
| Config & settings | **pydantic-settings** (v2) | Validates config, merges file + env + flags cleanly. |
| Secrets at rest | **keyring** (OS credential store) + **cryptography** (Fernet) for the session file | Avoids plaintext credentials; Fernet encrypts the persisted browser session. |
| TOTP / 2FA | **pyotp** | Generates GitHub 2FA codes from a stored TOTP secret so login can be non-interactive. |
| Packaging / env | **uv** | Fast, reproducible installs and lockfile; provides the virtualenv. |
| Testing | **pytest** (unit) + **Robot Framework** suites (end-to-end) | Unit-test services with a mocked browser; e2e suites drive a real browser against a test project. |
| Lint / format | **ruff** (lint + format), **mypy** (types), **robotframework-tidy** (`.robot` files) | Fast feedback for the implementer. |

> **Why Typer for the CLI instead of pure `.robot` suites?** `.robot` files are great for
> test flows but awkward as a user-facing CLI (argument parsing, help, exit codes). We use
> Typer for the interface and call `rpaframework`'s Browser library **from Python**
> (rpaframework libraries are plain Python classes and work outside `.robot`). Complex,
> reusable flows may still be authored as `.robot` suites and invoked programmatically.

---

## 4. High-level architecture

Four layers, each depending only on the one below it. Keep them separate so UI changes stay
contained in the Automation layer.

```
┌─────────────────────────────────────────────────────────────┐
│ CLI layer (Typer)                                            │
│   parses args/options, chooses output format, sets exit code │
└───────────────┬─────────────────────────────────────────────┘
                │ calls
┌───────────────▼─────────────────────────────────────────────┐
│ Service layer                                                │
│   BranchService, BackupService, DomainService, LogService,   │
│   UpgradeService, ProjectService, AuthService                │
│   = business operations, orchestration, validation           │
└───────────────┬─────────────────────────────────────────────┘
                │ uses
┌───────────────▼─────────────────────────────────────────────┐
│ Automation layer (Page Object Model)                         │
│   BrowserManager (owns Playwright context/session)           │
│   LoginPage, BranchesPage, BackupsPage, DomainsPage,         │
│   LogsPage, UpgradePage, ProjectSettingsPage                 │
│   = the ONLY code that knows CSS/XPath selectors & URLs      │
└───────────────┬─────────────────────────────────────────────┘
                │ supported by
┌───────────────▼─────────────────────────────────────────────┐
│ Cross-cutting: ConfigManager · SessionStore · Output/Formatter│
│                Logging · custom Exceptions                    │
└──────────────────────────────────────────────────────────────┘
```

**Rule for the implementer:** No CSS selectors, XPaths, or Odoo.sh URLs may appear anywhere
except in the Automation layer's Page Objects. Services speak in domain terms
("rebuild branch X"), never in "click button Y".

---

## 5. Authorization & authentication

This is the most fragile and security-sensitive part. Read carefully.

### 5.1 The auth chain

```
CLI → github.com login (service account) → Odoo.sh "Log in with GitHub" → Odoo.sh dashboard
```

### 5.2 Prerequisites (one-time human setup, documented for the user)

1. Create a **dedicated GitHub service account** (a bot user), separate from any human's
   account. Give it a strong password.
2. Enable **2FA (TOTP)** on that account and **save the TOTP secret** (the base32 string
   shown when setting up an authenticator app). The tool needs this secret to generate login
   codes. **[VERIFY]** whether the target GitHub org *requires* 2FA — if so this step is
   mandatory.
3. Grant the service account access to:
   - The **GitHub repository** linked to the Odoo.sh project (as a collaborator), and
   - The **Odoo.sh project** itself (as a project collaborator/admin, so it can perform
     management actions). **[VERIFY]** the exact permission level needed per operation.
4. Perform one **manual interactive login** to Odoo.sh with the service account to accept the
   GitHub OAuth authorization screen once (see 5.4).

### 5.3 Credential storage

Credentials are **never** committed or written in plaintext to the repo.

- Preferred: OS keyring via the `keyring` library, under service name `odoo-sh-cli`.
- Keys stored: `github_username`, `github_password`, `github_totp_secret`.
- CI / headless alternative: read from environment variables (see §7). Env vars take
  precedence when set.
- The persisted **browser session** (cookies + storage state) is written to
  `~/.config/odoo-sh-cli/session.enc`, **encrypted with Fernet**. The Fernet key derives
  from a machine-local key stored in the keyring. File permissions: `0600`.

### 5.4 Login flow (RPA, implemented in `LoginPage` + `AuthService`)

Pseudocode — implement each numbered step as a small, individually-testable method.

```
1.  Launch browser (headless unless --no-headless). If a valid session file exists,
    load its storage state and go to step 8 to verify.
2.  Navigate to https://www.odoo.sh/project        [VERIFY exact entry URL]
3.  Click "Sign in" / "Log in with GitHub".        [VERIFY selector/flow]
    (This redirects to github.com, or to Odoo login that offers a GitHub button.)
4.  On github.com login page:
      - fill #login_field with github_username
      - fill #password with github_password
      - submit
5.  If a 2FA/OTP page appears:
      - code = pyotp.TOTP(github_totp_secret).now()
      - fill the OTP field with `code`, submit
      - handle "verify device"/rate-limit variants gracefully
6.  If the GitHub OAuth "Authorize <app>" screen appears (usually only first time):
      - click "Authorize". [If not pre-authorized in 5.2, this is required.]
7.  Wait for redirect back to an Odoo.sh URL.
8.  Verify login: assert a known logged-in element is present on the Odoo.sh dashboard
    (e.g., the projects list / user menu). [VERIFY selector]
9.  On success: save storage state to the encrypted session file. Log "authenticated".
10. On failure: raise AuthenticationError with a clear, secret-free message.
```

**Session reuse:** Before every command, `AuthService.ensure_session()` loads the saved
session and does step 8's verification. If it fails (session expired), it re-runs the full
login flow once, then retries; if that also fails, it aborts with a clear error.

### 5.5 Security requirements (non-negotiable)

- Never log passwords, TOTP secrets, cookies, or tokens. Scrub them from any error output
  and from Playwright traces/screenshots.
- Session and any temp files: `0600`, stored under the user config dir, never in the repo.
- Support a `--no-persist-session` flag for shared/CI machines.
- Add `session.enc`, `.env`, and any screenshot/trace output dirs to `.gitignore`.
- **Compliance note:** automating GitHub login may be subject to GitHub's Terms of Service
  and anti-automation defenses (CAPTCHA, device verification). Document this risk; minimize
  logins by reusing the persisted session; surface a clear, actionable error if GitHub
  presents a CAPTCHA/device check that the tool cannot solve. **[VERIFY]** feasibility early
  (see plan Phase 1 spike).

---

## 6. CLI design

### 6.1 Invocation shape

```
odoo-sh [GLOBAL OPTIONS] <group> <command> [ARGUMENTS] [COMMAND OPTIONS]
```

Console entry point (defined in `pyproject.toml`): `odoo-sh`.

### 6.2 Global options

| Option | Type | Default | Meaning |
|--------|------|---------|---------|
| `--project, -p` | string | from config/env | Odoo.sh project name to operate on. Required unless set in config. |
| `--profile` | string | `default` | Named config profile (lets a user manage multiple projects/accounts). |
| `--config` | path | `~/.config/odoo-sh-cli/config.toml` | Config file location. |
| `--output, -o` | enum `table\|json\|plain` | `table` | Output format. `json` for scripting. |
| `--headless / --no-headless` | flag | `--headless` | Show the browser (debugging) or not. |
| `--timeout` | int (seconds) | `60` | Per-action wait timeout for the browser. |
| `--dry-run` | flag | off | Print what would be done for **mutating** commands; do not click anything destructive. |
| `--yes, -y` | flag | off | Skip confirmation prompts for destructive actions. |
| `--verbose, -v` | count | 0 | `-v` info, `-vv` debug logging. |
| `--version` | flag | — | Print version and exit. |

### 6.3 Output & exit codes

- `table`: human-friendly (Rich tables). `json`: machine-readable object/array. `plain`:
  minimal, one value per line (grep-friendly).
- Exit codes:
  - `0` success
  - `1` generic/unexpected error
  - `2` usage error (bad args) — Typer default
  - `3` authentication error
  - `4` operation failed on Odoo.sh side (e.g., rebuild rejected)
  - `5` timeout / element not found (likely UI drift)
- All errors print a single clear message to stderr; `-vv` adds a traceback and (optionally)
  a screenshot path for debugging.

### 6.4 Conventions

- **Destructive commands** (`branch delete`, `backup restore`) **must** prompt for
  confirmation unless `--yes` is given, and must honor `--dry-run`.
- **Long-running commands** (`branch rebuild`, `upgrade run`, `backup create`) support
  `--wait/--no-wait`; with `--wait` the command polls until the operation finishes or
  `--wait-timeout` elapses, then exits with a status-derived code.
- Every command that reads data supports all three `--output` formats.

---

## 7. Configuration & environment

### 7.1 Config file (`config.toml`)

```toml
default_project = "my-project"

[profiles.default]
project = "my-project"
headless = true
timeout = 60

[profiles.staging-admin]
project = "my-project-staging"
```

### 7.2 Environment variables (override config; used by CI)

| Env var | Purpose |
|---------|---------|
| `ODOO_SH_GITHUB_USERNAME` | Service account username |
| `ODOO_SH_GITHUB_PASSWORD` | Service account password |
| `ODOO_SH_GITHUB_TOTP_SECRET` | Base32 TOTP secret for 2FA |
| `ODOO_SH_PROJECT` | Default project name |
| `ODOO_SH_CONFIG` | Config file path |
| `ODOO_SH_HEADLESS` | `1`/`0` |

### 7.3 Precedence (highest wins)

`command-line flag` > `environment variable` > `config file (selected profile)` > `built-in default`.

---

## 8. Command reference

For **each** command below: synopsis, arguments, options, behavior, the RPA steps at a high
level, output, and error cases. Branch is referenced by its Git branch name.

> Notation: `<required>`, `[optional]`.

### 8.1 `auth` — authentication & session

- **`auth setup`** — Interactively prompt for and store GitHub username, password, and TOTP
  secret in the OS keyring. No browser. Output: confirmation (never echoes secrets).
- **`auth login`** — Run the full login flow (§5.4) and persist the session.
  - Options: `--no-persist-session`, `--no-headless` (useful to solve a one-time CAPTCHA).
  - Output: `Authenticated as <username>` / error code `3`.
- **`auth status`** — Load the saved session and verify it. Output: `valid`/`invalid` +
  expiry hint if known. Exit `0` if valid, `3` if not.
- **`auth logout`** — Delete the persisted session file. Output: confirmation.

### 8.2 `branch` — branch operations

- **`branch list`**
  - Args: none. Options: `[--stage production|staging|development]` filter.
  - Behavior: navigate to project, read the branch tree. Output columns: name, stage,
    status, last build time. RPA: `BranchesPage.list_branches()`.
- **`branch rebuild <branch>`**
  - Options: `[--wait]`, `[--wait-timeout <s>]`, `[--yes]`, `[--dry-run]`.
  - Behavior: trigger a rebuild of the branch's build. With `--wait`, poll build status
    until `done`/`failed`. RPA: open branch → History/Builds → "Rebuild".
  - Errors: `4` if Odoo.sh refuses (e.g., production rebuild guard).
- **`branch delete <branch>`**
  - Options: `[--yes]`, `[--dry-run]`. **Destructive** — confirm unless `--yes`.
  - Behavior: delete the branch (and its build) on Odoo.sh. RPA: branch settings → Delete →
    confirm. **[VERIFY]** whether this also deletes the Git branch.
- **`branch settings <branch>`**
  - Options: repeatable `--set key=value` (e.g., `--set worker_count=2`,
    `--set custom_domain_redirect=on`). `[--dry-run]`.
  - Behavior: open the branch's Settings, apply each key/value, save. **[VERIFY]** the exact
    set of editable per-branch settings and their control types (toggle/select/number).
    Output: the resulting settings.
- **`branch set-default-feature <branch>`** *(maps to "update the default feature branch
  configuration")*
  - Behavior: set/change which development branch is the default the platform uses for new
    feature branches / the default merge target. **[VERIFY]** exact meaning & location of
    this setting in the UI. Options: `[--dry-run]`.
- **`branch history <branch>`**
  - Options: `[--limit N]`. Output: recent builds (id/commit, status, timestamp).

### 8.3 `backup` — backups

- **`backup list <branch>`** — Output: available backups (id, comment, size, timestamp).
- **`backup create <branch>`**
  - Options: `[--comment "text"]`, `[--wait]`, `[--wait-timeout <s>]`.
  - Behavior: trigger a manual backup; optionally wait until it appears/completes.
- **`backup download <branch>`**
  - Options: `[--backup-id <id>]` (default: latest), `[--dest <path>]` (default: cwd),
    `[--type dump|filestore|full]` **[VERIFY]** available formats.
  - Behavior: download the backup artifact to `--dest`. Must handle a browser download and
    report the saved file path. This is the trickiest RPA step (file download handling in
    Playwright).
- **`backup restore <branch>`**
  - Options: `--from <backup-id | local-file-path>` (required), `[--yes]`, `[--dry-run]`,
    `[--wait]`. **Destructive** — overwrites the target branch's data; confirm unless
    `--yes`. **[VERIFY]** whether restore is done via UI upload or by selecting an existing
    backup, and whether cross-branch restore is allowed.

### 8.4 `domain` — instance domains

- **`domain list <branch>`** — Output: configured domains for the branch's instance.
- **`domain set <branch> <domain>`**
  - Options: `[--redirect-to <domain>]`, `[--www / --no-www]` **[VERIFY]**.
  - Behavior: add/configure a custom domain on the instance.
- **`domain remove <branch> <domain>`** — Options: `[--yes]`. Remove a configured domain.

### 8.5 `logs` — logs & monitoring

- **`logs show <branch>`**
  - Options: `[--type build|install|update|odoo|... ]` **[VERIFY]** available log types,
    `[--lines N]` (tail last N), `[--since <timestamp>]`.
  - Behavior: read the branch's log panel and print it.
- **`logs monitor <branch>`** *(maps to "check logs and monitor")*
  - Options: `[--type ...]`, `[--interval <s>]`.
  - Behavior: continuously stream new log lines (poll the UI on `--interval`) until Ctrl-C.
    Also usable to watch build health.

### 8.6 `upgrade` — version upgrades

- **`upgrade run <branch>`**
  - Options: `[--target-version <x.y>]` **[VERIFY]** whether target is selectable or fixed,
    `[--wait]`, `[--wait-timeout <s>]`, `[--yes]`.
  - Behavior: start an upgrade of the branch's database; optionally wait for completion.
- **`upgrade status <branch>`** — Output: current upgrade phase/status and progress.

### 8.7 `project` — project-level settings

- **`project info`** — Output: project name, plan, linked repo, stages summary.
- **`project settings`** — Output: current project settings (read).
- **`project set <key> <value>`** — Generic setter for a project setting. **[VERIFY]** the
  full editable set.
- **`project set-commit-status-token <token>`** *(maps to "update project settings like
  commit status token")*
  - Options: `[--dry-run]`. Behavior: set/rotate the commit status token in project settings.
    Treat the token as a secret in logs/output.

---

## 9. Automation layer design (Page Object Model)

- **`BrowserManager`**: owns the Playwright browser/context; applies `--headless`,
  `--timeout`, viewport, download path; loads/saves encrypted session; exposes `page`.
- **Page Objects**: one class per Odoo.sh screen. Each exposes intention-revealing methods
  (`BackupsPage.create_backup(comment)`), and is the **only** place selectors/URLs live.
- **Selector strategy** (to survive UI drift):
  1. Prefer stable, human-visible text and roles (Playwright `get_by_role`, `get_by_text`).
  2. Avoid brittle deep CSS/nth-child chains.
  3. Centralize every selector as a named constant at the top of its Page Object so updates
     are one-line.
- **Waiting**: rely on Playwright auto-waiting + explicit `expect(...).to_be_visible()`
  before acting. **Never** use fixed `sleep()` except as a last resort with a comment.
- **Screenshots/traces**: on failure, capture a screenshot + Playwright trace to the config
  dir (secrets scrubbed) to aid debugging; path shown only with `-vv`.

---

## 10. Error handling & resilience

- Custom exception hierarchy: `OdooShError` → {`AuthenticationError`, `OperationFailedError`,
  `ElementNotFoundError`/`UITimeoutError`, `ConfigError`}. Each maps to an exit code (§6.3).
- **Retry policy**: wrap navigation/read actions in a bounded retry (e.g., 3 attempts with
  backoff) for transient failures (slow load, stale element). **Do not** auto-retry
  destructive actions.
- **Idempotency guard**: before a mutating action, verify the current state (e.g., don't
  rebuild if a build is already in progress unless `--force`). **[VERIFY]** per operation.
- Every user-facing error is a single, secret-free, actionable line on stderr.

---

## 11. Logging & observability

- Standard `logging` + Rich handler. Levels controlled by `-v/-vv`.
- Structured context (project, branch, command) in each log line.
- A **secret filter** strips known secret values from all log records and Playwright output.
- Optional `--trace` flag to keep the Playwright trace file for post-mortem.

---

## 12. Testing strategy

- **Unit tests (pytest):** test Services with the Automation layer **mocked** (Page Objects
  replaced by fakes). Cover argument parsing, config precedence, output formatting, exit
  codes, confirmation/`--dry-run` behavior.
- **Contract tests for Page Objects:** small tests that assert selector constants exist and
  methods have the right signatures (cheap guard against accidental breakage).
- **End-to-end (Robot Framework + real browser):** run against a disposable **test Odoo.sh
  project** with the service account. Gated behind an env flag; not run in normal CI unless
  credentials are provided. Cover the read-only and reversible flows first.
- **CI:** run lint (ruff), types (mypy), unit tests on every push. E2E only on demand /
  nightly with secrets.

---

## 13. Proposed directory structure

```
odoo-sh-cli/
├── pyproject.toml
├── README.md
├── CLAUDE.md
├── specification.md            # original brief
├── detailed-specification.md   # this file
├── plan.md
├── src/odoo_sh_cli/
│   ├── __init__.py
│   ├── main.py                 # Typer app, global options, entry point
│   ├── commands/               # one module per group (auth, branch, backup, ...)
│   ├── services/               # BranchService, BackupService, ...
│   ├── automation/
│   │   ├── browser_manager.py
│   │   └── pages/              # login_page.py, branches_page.py, ...
│   ├── config.py               # pydantic-settings, profiles, precedence
│   ├── session.py              # encrypted session store
│   ├── output.py               # table/json/plain formatters
│   ├── errors.py               # exception hierarchy + exit codes
│   └── logging_setup.py
├── tests/                      # pytest unit tests
└── e2e/                        # Robot Framework suites (opt-in)
```

---

## 14. Assumptions, risks & open questions

All **[VERIFY]** items above, plus:

1. **UI stability** — Odoo.sh can change its UI at any time, breaking selectors. Mitigation:
   Page Object isolation + text/role selectors + a small e2e smoke suite.
2. **GitHub anti-automation** — CAPTCHA / device verification may block headless login.
   Mitigation: persistent session reuse; `--no-headless` fallback for one-time manual solve;
   consider a "bring your own session cookie" escape hatch. **Validate feasibility in the
   Phase 1 spike before building everything else.**
3. **Permissions** — exact Odoo.sh/GitHub permission level per operation is unknown until
   tested with the service account.
4. **Backup download/restore mechanics** — file download and (possibly) upload flows in the
   browser are the least predictable; treat as their own de-risking task.
5. **Rate limits / throttling** on repeated logins or actions. Reuse sessions; add backoff.
6. **Legal/ToS** — confirm automated access is permitted for the org's Odoo.sh subscription.

> **Guidance for the implementer:** resolve the **[VERIFY]** items by inspecting a real
> Odoo.sh project (Phase 1 discovery spike in `plan.md`) *before* hard-coding selectors or
> flows. Record findings back into this document.
