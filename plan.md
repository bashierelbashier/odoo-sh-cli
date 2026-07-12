# Odoo.sh CLI — Implementation Plan

> **How to read this plan.** Work proceeds in **phases**. Each phase lists its **goal**,
> **tasks** (small enough to finish in one sitting), **deliverables**, and **acceptance
> criteria** (how you know it's done). Do phases in order — later phases assume the earlier
> ones exist. Phase 1 contains a **spike** that must succeed before heavy building begins.
>
> This plan implements [`detailed-specification.md`](./detailed-specification.md). When a
> task says **[VERIFY]**, it means: inspect the real Odoo.sh UI, confirm the behavior, and
> write the finding back into the spec.
>
> Checkboxes are for tracking. Tick them as you go.

---

## Guiding principles

- **De-risk first.** Prove that GitHub→Odoo.sh automated login works (Phase 1 spike) before
  building the whole CLI. If it can't work headless, we need to know on day one.
- **Read before you write.** Build read-only commands (list, status, logs) before
  destructive ones. They're safe to test repeatedly and exercise the whole stack.
- **One selector home.** All CSS/XPath/URLs live only in Page Objects (see spec §4, §9).
- **Test the safe layers with mocks.** Services and CLI are unit-tested with the browser
  faked; only e2e tests touch a real browser.
- **Small, verifiable steps.** Every task ends in something runnable or testable.

---

## Phase 0 — Project setup & tooling

**Goal:** a runnable, linted, empty CLI skeleton.

**Tasks**
- [ ] Initialize `uv` project; create `pyproject.toml` (name `odoo-sh-cli`, entry point
      `odoo-sh = "odoo_sh_cli.main:app"`).
- [ ] Add dependencies: `typer`, `rich`, `rpaframework`, `pydantic-settings`, `keyring`,
      `cryptography`, `pyotp`. Dev: `pytest`, `ruff`, `mypy`, `robotframework-tidy`.
- [ ] Install Playwright browsers (`rpaframework`/Playwright post-install step).
- [ ] Create the directory structure from spec §13.
- [ ] Configure `ruff` (lint+format) and `mypy` in `pyproject.toml`.
- [ ] Add `.gitignore` (venv, `session.enc`, `.env`, screenshots/traces, `__pycache__`).
- [ ] `git init`; first commit.
- [ ] Minimal `main.py`: a Typer app with global options (§6.2) and `--version`, no
      subcommands yet.
- [ ] Set up CI (lint + mypy + pytest on push).

**Deliverables:** installable package; `odoo-sh --version` and `odoo-sh --help` work.
**Acceptance:** `uv run odoo-sh --help` prints global options; `ruff`, `mypy`, `pytest`
(zero tests) all pass in CI.

---

## Phase 1 — Auth foundation + feasibility spike ⚠️ **gate**

**Goal:** prove and implement automated GitHub→Odoo.sh login with a reusable session.

**Tasks**
- [ ] **Discovery spike (do this first, timebox it):** manually script, with
      `--no-headless`, the full login flow against a real project. Confirm you can:
      login with username/password, pass 2FA via `pyotp`, clear the OAuth screen, and land
      on the dashboard **without hitting a CAPTCHA/device block**. Record findings + all
      selectors/URLs into the spec's **[VERIFY]** slots. **If this fails, stop and escalate**
      — the whole approach depends on it (see spec §14 risk 2).
- [ ] Implement `ConfigManager` (pydantic-settings): file + env + flag precedence (§7).
- [ ] Implement `SessionStore`: Fernet-encrypted save/load of Playwright storage state;
      `0600` perms; key from keyring.
- [ ] Implement `BrowserManager`: launch/headless/timeout/download-dir; load & save session.
- [ ] Implement `LoginPage` (Page Object) encoding the flow from spec §5.4.
- [ ] Implement `AuthService`: `login()`, `ensure_session()` (reuse+verify+relogin-once),
      `logout()`, `status()`.
- [ ] Implement `auth` commands: `setup`, `login`, `status`, `logout` (§8.1).
- [ ] Add the **secret-scrubbing** log filter (§5.5, §11).

**Deliverables:** working `auth setup/login/status/logout`; encrypted session reused across
runs.
**Acceptance:** after `auth setup` then `auth login`, a second command reuses the session
without re-login; `auth status` reports `valid`; no secret ever appears in logs/traces.

---

## Phase 2 — Automation & CLI plumbing

**Goal:** shared scaffolding every feature command will reuse.

**Tasks**
- [ ] `BasePage` with common navigation, project-URL building, wait helpers, screenshot-on-
      failure.
- [ ] Navigation to a project + branch selection helper (used by most commands). **[VERIFY]**
      URL/routing per branch.
- [ ] `Output` formatter: `table`/`json`/`plain` (§6.3), plus a `render(rows, columns)` API.
- [ ] Exception hierarchy + exit-code mapping (§6.3, §10).
- [ ] Confirmation-prompt + `--dry-run` + `--yes` helpers for destructive/mutating commands.
- [ ] `--wait`/polling helper for long-running operations.
- [ ] Bounded retry/backoff wrapper for transient read failures (§10).
- [ ] Wire a `Context` object so commands get config, browser, services injected.

**Deliverables:** reusable helpers; a trivial internal command proves navigation + output.
**Acceptance:** unit tests cover output formats, exit-code mapping, precedence, and
dry-run/confirm logic (browser mocked).

---

## Phase 3 — Read-only commands (safe end-to-end)

**Goal:** exercise the full stack with non-destructive operations.

**Tasks**
- [ ] `branch list` (+ `--stage` filter) — `BranchesPage.list_branches()`.
- [ ] `branch history <branch>` — recent builds.
- [ ] `logs show <branch>` — `--type`, `--lines`, `--since`. **[VERIFY]** log types/panel.
- [ ] `project info` and `project settings` (read).
- [ ] `upgrade status <branch>` (read).
- [ ] `backup list <branch>` (read).

**Deliverables:** all listing/status commands working against a real project.
**Acceptance:** each returns correct data in all three output formats; unit tests with mocked
pages; manual check against the test project.

---

## Phase 4 — Backups (create / download / restore)

**Goal:** full backup lifecycle. Download/restore are the riskiest RPA flows — isolate them.

**Tasks**
- [ ] `backup create <branch>` — `--comment`, `--wait`. Verify it appears in `backup list`.
- [ ] `backup download <branch>` — handle Playwright download events; `--backup-id`,
      `--dest`, `--type`. Report saved path. **[VERIFY]** formats + download mechanics.
- [ ] `backup restore <branch> --from <id|file>` — **destructive**: confirm + `--dry-run` +
      `--wait`. **[VERIFY]** whether restore uses existing backup vs. file upload; whether
      cross-branch is allowed.

**Deliverables:** create/download/restore working on the test project.
**Acceptance:** create→list→download round-trips a real artifact; restore replays it (on a
throwaway dev branch); destructive guard + dry-run verified by tests.

---

## Phase 5 — Branch operations (mutating)

**Goal:** rebuild, delete, and settings.

**Tasks**
- [ ] `branch rebuild <branch>` — `--wait` polls build to done/failed; production guard.
      **[VERIFY]** rebuild control + status signals.
- [ ] `branch settings <branch> --set key=value` (repeatable) — map keys to UI controls
      (toggle/select/number). **[VERIFY]** editable set + control types.
- [ ] `branch set-default-feature <branch>` — **[VERIFY]** meaning/location of the setting.
- [ ] `branch delete <branch>` — **destructive**: confirm + dry-run. **[VERIFY]** side
      effects (Git branch?).

**Deliverables:** branch mutations working with guards.
**Acceptance:** rebuild reaches a terminal status with `--wait`; settings persist and read
back; delete removes the branch (tested on a throwaway branch); all destructive paths honor
`--dry-run`/`--yes`.

---

## Phase 6 — Domains

**Goal:** manage instance domains.

**Tasks**
- [ ] `domain list <branch>`.
- [ ] `domain set <branch> <domain>` — `--redirect-to`, `--www`. **[VERIFY]** options/flow.
- [ ] `domain remove <branch> <domain>` — confirm.

**Deliverables:** domain CRUD on the test project.
**Acceptance:** set→list shows the domain; remove clears it; verified against a dev branch.

---

## Phase 7 — Upgrades

**Goal:** run and track upgrades.

**Tasks**
- [ ] `upgrade run <branch>` — `--target-version` (**[VERIFY]** selectable?), `--wait`,
      confirm.
- [ ] Reuse `upgrade status` (Phase 3) for polling.

**Deliverables:** upgrade trigger + status.
**Acceptance:** on a dev branch, `upgrade run --wait` reaches a terminal state and reports it.

---

## Phase 8 — Project settings

**Goal:** project-level configuration.

**Tasks**
- [ ] `project set <key> <value>` — generic setter. **[VERIFY]** editable set.
- [ ] `project set-commit-status-token <token>` — treat token as secret.

**Deliverables:** project settings mutations.
**Acceptance:** a changed setting reads back via `project settings`; token never logged.

---

## Phase 9 — Monitoring & robustness

**Goal:** continuous monitoring and production hardening.

**Tasks**
- [ ] `logs monitor <branch>` — poll on `--interval`, stream new lines until Ctrl-C; clean
      shutdown.
- [ ] Idempotency guards (§10) across mutating commands (e.g., skip rebuild if one is
      running unless `--force`).
- [ ] Failure artifacts: screenshot + trace on error (secrets scrubbed), path shown with
      `-vv`; `--trace` flag.
- [ ] Tune retries/backoff and timeouts from real-world runs.

**Deliverables:** resilient tool suitable for scheduled/CI use.
**Acceptance:** monitor streams updates and exits cleanly; injected transient failures
recover via retry; failure artifacts are produced and secret-free.

---

## Phase 10 — Testing, docs, packaging, release

**Goal:** ship it.

**Tasks**
- [ ] Broaden pytest unit coverage across services/commands (mocked browser).
- [ ] Author Robot Framework e2e smoke suite (opt-in, real test project) for read-only +
      reversible flows.
- [ ] Wire e2e into CI as an on-demand/nightly job gated on secrets.
- [ ] `README.md`: install, `auth setup`, config/profiles, env vars, command examples,
      the ToS/CAPTCHA caveats.
- [ ] Update `CLAUDE.md` with the now-real build/test/lint/run commands (replace its
      "greenfield" section).
- [ ] Package + version (tag); optional publish.

**Deliverables:** documented, tested, releasable v1.
**Acceptance:** CI green (lint+types+unit); e2e smoke passes on demand; README lets a new
user go from zero to a working command.

---

## Milestones (rollup)

| Milestone | Phases | Meaning |
|-----------|--------|---------|
| **M0 — Skeleton** | 0 | CLI runs, tooling/CI in place. |
| **M1 — Login proven** ⚠️ | 1 | Automated GitHub→Odoo.sh login + session reuse works. **Gate.** |
| **M2 — Read-only** | 2–3 | Full stack works for listing/status/logs. |
| **M3 — Data ops** | 4 | Backup lifecycle. |
| **M4 — Full control** | 5–8 | Branches, domains, upgrades, project settings. |
| **M5 — Production-ready** | 9–10 | Monitoring, hardening, tests, docs, release. |

---

## Cross-cutting definition of done (every command)

- Works in `table`, `json`, and `plain` output.
- Mutating/destructive commands honor `--dry-run`, `--yes`, and confirmation.
- Long-running commands support `--wait` with a sensible timeout and status-derived exit
  code.
- Has unit tests with the browser mocked; selectors live only in a Page Object.
- Emits no secrets in logs, output, screenshots, or traces.
- Errors produce a single clear stderr line and the correct exit code (spec §6.3).
