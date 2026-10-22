#!/usr/bin/env bash
#
# Example cron wrapper for build-calendar-events (Milestone 3).
#
# This REGENERATES the combined feed file on a schedule using the same command
# the GitHub Actions workflow runs. It does NOT publish anything: writing
# public/sports.ics on this machine does not update a hosted subscription URL.
# GitHub Actions -> GitHub Pages remains the supported end-to-end publisher.
# To serve this file yourself you must additionally host the output directory
# over HTTPS (out of scope here).
#
# Install (run roughly monthly, 07:17 on the 1st):
#   crontab -e
#   17 7 1 * *  /absolute/path/to/build-calendar-events/docs/cron-example.sh
#
# cron runs with a minimal environment, so everything below uses absolute paths
# and loads secrets explicitly rather than relying on an interactive shell.

set -euo pipefail

# --- Edit these absolute paths for your machine ----------------------------
PROJECT_DIR="/absolute/path/to/build-calendar-events"
PYTHON="${PROJECT_DIR}/.venv/bin/python"
LOG_FILE="${PROJECT_DIR}/data/feed-cron.log"
# ---------------------------------------------------------------------------

cd "${PROJECT_DIR}"

# Load secrets from .env if present (feed generation itself needs none, but the
# same pattern applies if you extend this wrapper to email as well).
if [ -f "${PROJECT_DIR}/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "${PROJECT_DIR}/.env"
  set +a
fi

{
  echo "----- feed run $(date -u +%Y-%m-%dT%H:%M:%SZ) -----"
  # The feed build fails closed (non-zero exit) if a source breaks or returns
  # no events; `set -e` above propagates that so cron can report the failure.
  "${PYTHON}" "${PROJECT_DIR}/main.py" feed
  echo "feed regenerated: ${PROJECT_DIR}/public/sports.ics"
} >> "${LOG_FILE}" 2>&1
