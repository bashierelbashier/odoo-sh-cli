# Test Plan (Uncensored) — Live Actions on `odooshkonto-demo-project`

> **Scope.** This plan drives **real, unguarded actions** — including destructive ones —
> against the live Odoo.sh project owned by the `odooshkonto` service account. The project is
> a throwaway demo (Odoo 19.0, trial, no sensitive data), so we deliberately execute the
> mutating flows that are still marked `[VERIFY-ACTION]` in the Page Objects, observe them in
> the real UI, and record the confirmed selectors/behaviour back into the code and spec.
>
> **Goal.** Confirm every command end-to-end, promote each `[VERIFY-ACTION]` selector to
> "verified", and surface gaps between the spec and the implementation.
>
> **This file is a plan, not a run log.** Execute the phases in order; tick the checkboxes and
> paste observations as you go. Nothing here runs automatically.

---

## 0. Known facts about the target

| Fact | Value |
|------|-------|
| Project name | `odooshkonto-demo-project` |
| Linked repo | `odooshkonto/demo-project` |
| Odoo version | 19.0 |
| Branches at start | `main` only, on the **Production** stage |
| Account 2FA | none (plain user/password login) |
| Trial | ~29 days at time of discovery (2026-07-02) |

**Consequence:** `main` is the *production* branch and the only one. Odoo.sh does not let you
delete a production branch, and rebuilding/restoring/ upgrading `main` churns the only live
instance. So **all branch-scoped destructive tests run on a disposable branch**, created in
Phase 1 and deleted in Phase 9. `main` is used only for read-only and (optionally) rebuild.

---

## 1. Preconditions & safety rig

- [ ] **Credentials in env** (never committed):
  ```bash
  export ODOO_SH_GITHUB_USERNAME=odooshkonto
  export ODOO_SH_GITHUB_PASSWORD='<password from odooshkonto.txt>'   # do NOT paste it into this file
  export ODOO_SH_PROJECT=odooshkonto-demo-project
  ```
- [ ] **Browser installed:** `uv run rfbrowser init` has been run.
- [ ] **Observe while testing:** add `--no-headless` to watch the UI, and `-vv` for debug logs
      + screenshot-on-failure paths. Example:
      `uv run odoo-sh --no-headless -vv branch list`.
- [ ] **Session primed:** `uv run odoo-sh auth login` succeeds; `auth status` → `valid`.
- [ ] **Baseline snapshot:** run `uv run odoo-sh -o json branch list`, `project info`,
      `project settings`, `backup list main`, `branch settings main` and save the output to
      compare against the end state.

### 1.1 Create the disposable sandbox branch

The CLI has no "create branch" command yet (see Gaps §11). Create a Development branch by
pushing to the linked GitHub repo; Odoo.sh auto-builds it under **Development**.

```bash
# One-time, in a scratch dir (uses the env vars set above; avoids embedding the password):
git clone "https://${ODOO_SH_GITHUB_USERNAME}:${ODOO_SH_GITHUB_PASSWORD}@github.com/odooshkonto/demo-project.git"
cd demo-project
git checkout -b test-sandbox
git commit --allow-empty -m "test-sandbox: CLI verification branch"
git push origin test-sandbox
```

- [ ] After ~1–2 min, `uv run odoo-sh branch list` shows `test-sandbox` (Development).
- [ ] Wait until its first build is green before running branch tests against it.

> From here, `SANDBOX=test-sandbox`. Destructive branch tests target `$SANDBOX`, never `main`.

---

## 2. Auth (`auth`)

| # | Command | Expected | Verify |
|---|---------|----------|--------|
| 2.1 | `odoo-sh auth logout` | "Session cleared." | `~/.config/odoo-sh-cli/session.enc` removed |
| 2.2 | `odoo-sh auth login` | "Authenticated as odooshkonto" (exit 0) | session file re-created, `0600` |
| 2.3 | `odoo-sh auth status` | `session: valid` (exit 0) | reuse works with creds unset in env |
| 2.4 | `odoo-sh --no-persist-session auth login` | authenticates | no session file written |
| 2.5 | `odoo-sh auth setup` (interactive) | stores creds; secrets not echoed | keyring holds username/password |

- [ ] All pass. (2.1–2.3 already verified live; re-confirm.)

---

## 3. Read-only commands (safe on `main`)

| # | Command | Expected |
|---|---------|----------|
| 3.1 | `odoo-sh -o json branch list` | array incl. `{name: main, ...}` and `test-sandbox` |
| 3.2 | `odoo-sh branch list --stage production` | only `main` |
| 3.3 | `odoo-sh branch list --stage development` | only `test-sandbox` |
| 3.4 | `odoo-sh branch history main --limit 10` | recent build/stage-change events |
| 3.5 | `odoo-sh branch connect-info main` | Git remote / SSH details (may be partial) |
| 3.6 | `odoo-sh -o json project info` | name, repo `odooshkonto/demo-project`, version 19.0 |
| 3.7 | `odoo-sh project settings` | key/value project settings |
| 3.8 | `odoo-sh logs show main --lines 20` | last 20 real server log lines |
| 3.9 | `odoo-sh backup list main` | backups list (may be empty on trial) |
| 3.10 | `odoo-sh upgrade status main` | current upgrade status/panel text |
| 3.11 | `odoo-sh -o table/plain/json ...` on 3.1 | all three formats render correctly |

- [ ] 3.1–3.4, 3.6, 3.8 already verified live — re-confirm with `test-sandbox` present.
- [ ] Record whether 3.5, 3.7, 3.9, 3.10 return meaningful data; refine extractors if thin.

---

## 4. Branch settings (mutate + revert on `$SANDBOX`)

| # | Command | Expected | Verify / rollback |
|---|---------|----------|-------------------|
| 4.1 | `odoo-sh branch settings $SANDBOX` | current settings key/values | note original values |
| 4.2 | `odoo-sh --dry-run branch settings $SANDBOX --set <key>=<val>` | prints `[dry-run] would set ...`, no change | UI unchanged |
| 4.3 | `odoo-sh branch settings $SANDBOX --set <key>=<val>` | returns updated settings | reload UI: value persisted |
| 4.4 | revert: `odoo-sh branch settings $SANDBOX --set <key>=<original>` | back to baseline | UI shows original |

- [ ] Pick a low-risk setting observed in 4.1 (e.g. a worker count / toggle). **[VERIFY-ACTION]**
      confirm the label→control mapping in `branches_page.py::_SET_SETTING_JS` (checkbox vs
      select vs text) and that "Save" persists. Record the real settable keys + control types.

---

## 5. Backups lifecycle (on `$SANDBOX`)

| # | Command | Expected | Verify |
|---|---------|----------|--------|
| 5.1 | `odoo-sh --dry-run backup create $SANDBOX` | dry-run message, no backup | list unchanged |
| 5.2 | `odoo-sh backup create $SANDBOX --comment "cli-test"` | "Backup requested" | appears in `backup list` after it completes |
| 5.3 | `odoo-sh backup list $SANDBOX` | includes the `cli-test` backup | note its id/label |
| 5.4 | `odoo-sh backup download $SANDBOX --dest ./bk` | prints saved path | file exists, non-zero size, is a valid dump/zip |
| 5.5 | `odoo-sh --dry-run backup restore $SANDBOX --from <id>` | dry-run message, no restore | instance untouched |
| 5.6 | `odoo-sh --yes backup restore $SANDBOX --from <id>` | "Restore started" | UI shows restore/build; data replaced |

- [ ] **[VERIFY-ACTION]** confirm in `backups_page.py`: the "Create Backup" flow (dialog? comment
      field?), the per-row **Download** control + the `Promise To Wait For Download` mechanics
      (does it need `--type dump|filestore|full`?), and the **Restore** flow (existing backup vs
      upload; is cross-branch allowed?). Record findings.
- [ ] Note the available backup **types/formats** and whether download offers a choice.

---

## 6. Rebuild

| # | Command | Expected | Verify |
|---|---------|----------|--------|
| 6.1 | `odoo-sh --dry-run branch rebuild $SANDBOX` | dry-run message | no rebuild |
| 6.2 | `odoo-sh --yes branch rebuild $SANDBOX` | "Rebuild triggered" | UI: a new build starts; history shows it |
| 6.3 | (optional) `odoo-sh --yes branch rebuild main` | production rebuild | confirm guard/behaviour on prod |

- [ ] **[VERIFY-ACTION]** confirm the "Rebuild" control location (history vs builds panel) and
      whether a production rebuild needs a confirm dialog (`branches_page.py::rebuild`). Note if
      a `--wait` for build completion is worth adding (see Gaps §11).

---

## 7. Domains (on `$SANDBOX`)

| # | Command | Expected | Verify |
|---|---------|----------|--------|
| 7.1 | `odoo-sh domain list $SANDBOX` | configured domains (likely the default `*.odoo.com`) | baseline |
| 7.2 | `odoo-sh --dry-run domain set $SANDBOX cli-test.example.com` | dry-run message | no change |
| 7.3 | `odoo-sh domain set $SANDBOX cli-test.example.com` | "Domain set" | appears in `domain list` |
| 7.4 | `odoo-sh --yes domain remove $SANDBOX cli-test.example.com` | "Domain removed" | gone from `domain list` |

- [ ] **[VERIFY-ACTION]** confirm domains live in the branch **Settings** panel; find the real
      input field + add/remove controls (`domains_page.py`). **Caveat:** Odoo.sh may reject a
      domain you don't own or restrict custom domains on a trial — if so, record the exact error
      and treat 7.3/7.4 as "attempted; blocked by platform" rather than a tool bug. Also check
      the spec's `--redirect-to` / `--www` options (Gaps §11).

---

## 8. Upgrade (on `$SANDBOX`)

| # | Command | Expected | Verify |
|---|---------|----------|--------|
| 8.1 | `odoo-sh upgrade status $SANDBOX` | status panel text | baseline |
| 8.2 | `odoo-sh --dry-run upgrade run $SANDBOX` | dry-run message | no upgrade |
| 8.3 | `odoo-sh --yes upgrade run $SANDBOX` | "Upgrade started" | UI shows upgrade job |

- [ ] **[VERIFY-ACTION]** confirm the upgrade trigger control + status text
      (`upgrade_page.py`). **Caveat:** already on the latest 19.0 and/or trial may make upgrade a
      no-op or unavailable — record the actual UI state (e.g., "no target version selectable").

---

## 9. Project settings

| # | Command | Expected | Verify / rollback |
|---|---------|----------|-------------------|
| 9.1 | `odoo-sh project settings` | current settings (baseline) | save original token state |
| 9.2 | `odoo-sh --dry-run project set-commit-status-token cli-dummy-token` | dry-run message | no change |
| 9.3 | `odoo-sh project set-commit-status-token cli-dummy-token` | "token updated"; token **not** echoed in output/logs | UI: field populated |
| 9.4 | revert: set the token back to its original value (or blank) | restored | UI reflects revert |

- [ ] **[VERIFY-ACTION]** confirm the commit-status-token field selector
      (`project_page.py::SEL_TOKEN_INPUT`) and that the token never appears in stdout, `-vv`
      logs, or Playwright output (secret-scrubbing works).

---

## 10. Destructive: delete the sandbox (cleanup)

| # | Command | Expected | Verify |
|---|---------|----------|--------|
| 10.1 | `odoo-sh --dry-run branch delete $SANDBOX` | dry-run message | branch still present |
| 10.2 | `odoo-sh branch delete $SANDBOX` then answer **n** | Abort (exit ≠ 0) | branch still present |
| 10.3 | `odoo-sh --yes branch delete $SANDBOX` | "Deleted branch" | gone from `branch list` |

- [ ] **[VERIFY-ACTION]** confirm the Delete control + confirm dialog on the branch settings
      panel (`branches_page.py::delete`). Record **side effects**: does deleting the Odoo.sh
      branch also delete the Git branch on GitHub? If not, delete `test-sandbox` on GitHub too:
      `git push origin --delete test-sandbox`.
- [ ] Confirm `branch delete main` is refused by the platform (production guard) — attempt only
      to document the error; it should fail safely.

---

## 11. Global-option matrix (spot-check across the above)

- [ ] `-o table` / `-o json` / `-o plain` on a read command — all valid, JSON parses.
- [ ] `--dry-run` blocks every mutating command (4.2, 5.1, 5.5, 6.1, 7.2, 8.2, 9.2, 10.1).
- [ ] `--yes` skips confirmation on every destructive command (5.6, 7.4, 8.3, 10.3).
- [ ] confirmation **declined** aborts (10.2) — no action taken.
- [ ] `--timeout 30` and `--timeout 120` both honoured.
- [ ] `--profile <name>` selects a config profile; `--project` overrides env.
- [ ] `-v` / `-vv` change log verbosity; `-vv` prints a screenshot path on a forced failure.
- [ ] Exit codes: success `0`; bad args `2`; auth failure `3` (test by logging out + bad
      password); operation refused `4` (e.g. production delete); UI timeout `5`.

---

## 12. Gaps found vs. spec (fill in while testing)

Implemented commands differ from `detailed-specification.md` §8 in places. Confirm and log:

- [ ] **`branch set-default-feature`** — in the spec, **not implemented** (we have
      `connect-info` instead). Decide: implement or drop.
- [ ] **`--wait` / `--wait-timeout`** — spec wants it on `rebuild`, `backup create`,
      `upgrade run`; currently absent. The `poll()` helper exists to back it.
- [ ] **`backup download --type dump|filestore|full`** — spec option not implemented; confirm
      what the UI actually offers.
- [ ] **`domain set --redirect-to` / `--www`** — spec options not implemented.
- [ ] **`logs show --type` / `--since`**, **`logs monitor --type`** — not implemented; confirm
      the real log-type selector in the panel.
- [ ] **`project set <key> <value>`** (generic setter) — spec has it; only
      `set-commit-status-token` is implemented.
- [ ] **UI actions with no command yet:** Fork, Merge, SSH, SQL console, Submodule, and the
      **TOOLS** panel actions (e.g. neutralize/download-dump). List what TOOLS exposes and
      decide which to add.

---

## 13. Exit criteria

- [ ] Every command in §§2–10 executed against the live project with the expected result.
- [ ] Each `[VERIFY-ACTION]` selector either confirmed (comment updated, dated) or fixed.
- [ ] Findings written back into `branches/backups/domains/upgrade/project` Page Objects and
      the `[VERIFY]` slots in `detailed-specification.md`.
- [ ] Gaps in §12 triaged (implement / defer / drop) and captured as follow-up tasks.
- [ ] Project returned to a clean state: sandbox branch deleted (Odoo.sh + GitHub), test
      backups/domains removed, commit-status-token reverted. Baseline (§1) matches end state
      except for intended, documented differences.
