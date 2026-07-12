#!/usr/bin/env bash
# Bootstrap a development environment for odoo-sh-cli.
#
#   ./setup.sh            # full dev setup (uv, deps, browser, pre-commit)
#   ./setup.sh --no-dev   # runtime only (no dev tools / pre-commit)
#
# Idempotent: safe to re-run.
set -euo pipefail

DEV=1
[[ "${1:-}" == "--no-dev" ]] && DEV=0

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*"; }

# 1. Ensure uv is installed.
if ! command -v uv >/dev/null 2>&1; then
  info "Installing uv (https://docs.astral.sh/uv/)"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # Make uv available in this shell for the rest of the script.
  export PATH="$HOME/.local/bin:$PATH"
fi
info "uv $(uv --version | awk '{print $2}')"

# 2. Install dependencies into a project virtualenv.
if [[ "$DEV" == "1" ]]; then
  info "Installing dependencies (including dev tools)"
  uv sync
else
  info "Installing runtime dependencies only"
  uv sync --no-dev
fi

# 3. Download the Playwright browser used for automation (required).
info "Initializing the automation browser (rfbrowser init)"
uv run rfbrowser init || warn "rfbrowser init reported warnings; the browser may still work."

# 4. Developer conveniences.
if [[ "$DEV" == "1" ]]; then
  info "Installing pre-commit hooks"
  uv run pre-commit install
  uv run pre-commit install --hook-type pre-push
fi

info "Done. Try:  uv run odoo-sh --help"
if [[ "$DEV" == "1" ]]; then
  echo "     Next: uv run odoo-sh auth setup   # store your GitHub credentials"
fi
