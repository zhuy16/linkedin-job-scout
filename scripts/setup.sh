#!/usr/bin/env bash
# =============================================================================
#  scripts/setup.sh — one-time (and re-runnable) setup for LinkedIn Job Scout
#
#  What it does:
#    1. Copies example files to their private locations if not already done
#    2. Installs / updates the macOS launchd scheduler from config/search.yaml
#
#  Run it:
#    bash scripts/setup.sh
#
#  Re-run any time you change schedule_hour or schedule_minute in
#  config/search.yaml to apply the new time.
# =============================================================================

set -e
cd "$(dirname "$0")/.."   # always run from project root

BOLD="\033[1m"; GREEN="\033[32m"; YELLOW="\033[33m"; RED="\033[31m"; RESET="\033[0m"

info()    { echo -e "${GREEN}✓${RESET} $*"; }
warn()    { echo -e "${YELLOW}!${RESET} $*"; }
header()  { echo -e "\n${BOLD}$*${RESET}"; }
die()     { echo -e "${RED}✗ ERROR:${RESET} $*"; exit 1; }

# ── Step 1: Copy example files if missing ─────────────────────────────────────
header "Step 1 — Private files"

if [ ! -f secrets/.env ]; then
    cp secrets/.env.example secrets/.env
    warn "Created secrets/.env from template — open it and fill in your credentials."
else
    info "secrets/.env already exists — skipping."
fi

if [ ! -f private/profile_summary.txt ]; then
    cp private/profile_summary.example.txt private/profile_summary.txt
    warn "Created private/profile_summary.txt from template — open it and replace"
    warn "every placeholder with your real background, skills, and preferences."
    warn "The more specific you are, the better the LLM scoring quality."
else
    info "private/profile_summary.txt already exists — skipping."
fi

# ── Step 2: Read schedule from config/search.yaml ─────────────────────────────
header "Step 2 — Reading schedule from config/search.yaml"

HOUR=$(python3 -c "import yaml; c=yaml.safe_load(open('config/search.yaml')); print(c.get('schedule_hour', 8))" 2>/dev/null) \
    || die "Could not read config/search.yaml — is PyYAML installed? Run: pip install pyyaml"
MINUTE=$(python3 -c "import yaml; c=yaml.safe_load(open('config/search.yaml')); print(c.get('schedule_minute', 0))")

# Format for display
printf -v TIME_DISPLAY "%02d:%02d" "$HOUR" "$MINUTE"
info "Schedule: daily at ${TIME_DISPLAY}"

# ── Step 3: Install / update launchd agent (macOS only) ───────────────────────
header "Step 3 — macOS launchd scheduler"

if [[ "$(uname)" != "Darwin" ]]; then
    warn "Not macOS — skipping launchd setup. Use cron or your OS scheduler manually."
    exit 0
fi

PROJECT_DIR="$(pwd)"
PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python"
PLIST_DEST="${HOME}/Library/LaunchAgents/com.jobscout.daily.plist"

# Verify venv python exists
if [ ! -f "$PYTHON_BIN" ]; then
    die ".venv not found. Create it first:\n  python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
fi

# Unload existing agent if present (so we can replace it cleanly)
if launchctl list | grep -q "com.jobscout.daily" 2>/dev/null; then
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    info "Unloaded existing agent."
fi

# Fill in the plist template with real values
mkdir -p "${HOME}/Library/LaunchAgents"
sed \
    -e "s|PLACEHOLDER_PYTHON|${PYTHON_BIN}|g" \
    -e "s|PLACEHOLDER_PROJECT_DIR|${PROJECT_DIR}|g" \
    -e "s|<integer>PLACEHOLDER_HOUR</integer>|<integer>${HOUR}</integer>|g" \
    -e "s|<integer>PLACEHOLDER_MINUTE</integer>|<integer>${MINUTE}</integer>|g" \
    scheduler/com.jobscout.daily.plist > "$PLIST_DEST"

# Load the agent
launchctl load "$PLIST_DEST"

info "Scheduler installed — Job Scout will run silently every day at ${TIME_DISPLAY}."
info "Logs: ${PROJECT_DIR}/data/launchd.log"
echo ""
echo -e "  Trigger now:  ${BOLD}launchctl start com.jobscout.daily${RESET}"
echo -e "  Verify:       ${BOLD}launchctl list | grep jobscout${RESET}"
echo -e "  Disable:      ${BOLD}launchctl unload ~/Library/LaunchAgents/com.jobscout.daily.plist${RESET}"
echo ""

# ── Done ──────────────────────────────────────────────────────────────────────
header "Done!"
if [ ! -s secrets/.env ] || grep -q "your_linkedin_email" secrets/.env; then
    echo ""
    warn "Reminder: open ${BOLD}secrets/.env${RESET} and fill in your credentials."
fi
if grep -q "your field" private/profile_summary.txt 2>/dev/null; then
    echo ""
    warn "Reminder: open ${BOLD}private/profile_summary.txt${RESET} and fill in your background."
fi
