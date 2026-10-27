#!/usr/bin/env bash
# Run from your local Cape Ranch Git repository *after* extracting ZIP into it.
set -euo pipefail
if [[ ! -d .git || ! -f backend/main.py ]]; then
 echo 'ERROR: Run from Cape Ranch repository root (e.g. ~/Desktop/Ranching_Project_2026)' >&2;exit 2
fi
if [[ "$(git branch --show-current)" != 'main' ]]; then
 echo 'ERROR: Please switch to the main branch before deployment.' >&2;exit 2
fi
bash INSTALL_CAPE_LANDING_V2.sh
bash VERIFY_CAPE_LANDING_V2.sh
printf '\nFiles going to GitHub:\n'
git add backend/main.py frontend/shared/app.js frontend/landing.html \
  frontend/shared/landing-v2.css frontend/shared/landing-v2.js \
  frontend/public/images/landing-v2/ \
  tests/test_landing_v2.py docs/CAPE_LANDING_V2_README.md \
  INSTALL_CAPE_LANDING_V2.sh VERIFY_CAPE_LANDING_V2.sh \
  DEPLOY_CAPE_LANDING_V2_GITBASH.sh
git diff --cached --check
git diff --cached --stat
if git diff --cached --quiet;then
 echo 'No new changes to commit; already installed.';exit 0
fi
git commit -m "Add Cape Ranch public landing page - Design 02"
git push origin main
printf '\nGitHub push complete. Render auto-deployment should start.\n'
