# Contributing

Thanks for your interest in improving `odoo-sh-cli`.

## Getting started

```bash
git clone <your-fork-url>
cd odoo-sh-cli
./setup.sh          # installs uv, deps, the automation browser, and pre-commit hooks
```

Or step by step: `make install && make browser && make hooks`.

## Development workflow

- Run the checks before pushing: `make check` (lint + types + tests + format check).
- Pre-commit runs ruff and mypy on commit, and pytest on push. Run all hooks
  manually with `pre-commit run --all-files`.
- Keep changes small and match the surrounding style.

## Architecture rules (important)

The code is layered (see `detailed-specification.md` §4). Respect the boundaries:

- **`commands/`** — Typer commands. Parse args, choose output, no Odoo.sh knowledge.
- **`services/`** — business operations in domain terms ("rebuild branch X").
- **`automation/pages/`** — Page Objects. **The ONLY place** CSS/XPath selectors,
  JS extraction snippets, and Odoo.sh URLs may live. When the Odoo.sh UI changes,
  only these files should need updating.

Selectors verified against the live UI are dated in comments; unverified action
selectors are marked `[VERIFY-ACTION]`.

## Tests

- Unit tests (`tests/`) fake the browser/service layer — no network, no browser.
- Add tests for new commands (argument parsing, output, dry-run/confirm) and for
  any new parsing logic in Page Objects.
- The opt-in Robot Framework e2e suite (`e2e/`) needs real credentials and a
  disposable test project; do not run destructive flows against production data.

## Security

Never commit credentials or sessions. Secrets are loaded from the OS keyring or
`ODOO_SH_*` environment variables and are scrubbed from logs. `.env`,
`session.enc`, and local credential files are gitignored.
