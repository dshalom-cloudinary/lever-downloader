#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
#  Lever Resume Downloader – One-step install & run
# ──────────────────────────────────────────────────────────────────
#  Usage (first time):
#    curl -sL https://raw.githubusercontent.com/dshalom-cloudinary/lever-downloader/desktop/install-and-run.sh | bash
#
#  Or clone the repo and run:
#    ./install-and-run.sh
# ──────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_URL="https://github.com/dshalom-cloudinary/lever-downloader.git"
BRANCH="desktop"
INSTALL_DIR="$HOME/.lever-downloader"

# ── Colours ───────────────────────────────────────────────────────
BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
DIM="\033[2m"
RESET="\033[0m"

info()  { echo -e "  ${GREEN}✓${RESET} $*"; }
warn()  { echo -e "  ${YELLOW}!${RESET} $*"; }
fail()  { echo -e "  ${RED}✗ $*${RESET}"; exit 1; }
step()  { echo -e "\n${BOLD}▸ $*${RESET}"; }

# ── 1. Find Python 3 ─────────────────────────────────────────────
step "Checking for Python 3 ..."

PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        version=$("$candidate" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 9 ]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    fail "Python 3.9+ is required but was not found.\n       Install it with:  brew install python@3.10"
fi
info "Using $($PYTHON --version) at $(which $PYTHON)"

# ── 2. Clone or update the repository ────────────────────────────
step "Setting up project in $INSTALL_DIR ..."

if [ -d "$INSTALL_DIR/.git" ]; then
    info "Repository already exists – pulling latest changes ..."
    cd "$INSTALL_DIR"
    git fetch origin "$BRANCH" --quiet
    git checkout "$BRANCH" --quiet 2>/dev/null || true
    git reset --hard "origin/$BRANCH" --quiet
else
    info "Cloning repository ..."
    git clone --branch "$BRANCH" --single-branch --quiet "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# ── 3. Create / reuse virtual environment ────────────────────────
step "Setting up Python environment ..."

VENV_DIR="$INSTALL_DIR/.venv"

if [ ! -f "$VENV_DIR/bin/activate" ]; then
    info "Creating virtual environment ..."
    "$PYTHON" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
info "Virtual environment active"

# ── 4. Install dependencies ──────────────────────────────────────
step "Installing dependencies ..."

pip install --quiet --upgrade pip
pip install --quiet playwright

# ── 5. Ensure Chromium is available ──────────────────────────────
step "Checking Chromium browser ..."

if ! python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); p.chromium.executable_path; p.stop()" 2>/dev/null; then
    warn "Chromium not found – installing (one-time, ~150 MB) ..."
    python -m playwright install chromium
fi
info "Chromium is ready"

# ── 6. Launch the downloader ─────────────────────────────────────
step "Launching Lever Resume Downloader ..."
echo ""

python run.py
