#!/usr/bin/env bash
# Cape Ranch Design 02 v2.2 — zero backend or database changes.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
if [[ ! -d .git || ! -f frontend/landing.html || ! -f frontend/shared/landing-v2.css ]]; then
  echo 'ERROR: Run in Cape Ranch Git repository root after extracting ZIP there.' >&2
  exit 2
fi
if [[ "$(git branch --show-current)" != main ]]; then
  echo 'ERROR: Check out main branch and review changes before publishing.' >&2
  exit 2
fi
if ! git diff --cached --quiet; then
  echo 'ERROR: Other changes already staged; review them first. Nothing was committed.' >&2
  exit 2
fi
if ! grep -Fq "FileResponse(FRONTEND/'landing.html')" backend/main.py; then
  echo 'ERROR: Public / route must already serve frontend/landing.html. Run previous landing installer before this enhancement.' >&2
  exit 2
fi
if ! grep -Fq "@app.get('/login',include_in_schema=False)" backend/main.py; then
  echo 'ERROR: /login compatibility route missing. Stop and review backend/main.py.' >&2
  exit 2
fi
if command -v node >/dev/null 2>&1; then
  node --check frontend/shared/landing-v2.js
else
  echo 'WARNING: Node.js not installed; skipping JS syntax check.'
fi
if [[ -f backend/.venv/Scripts/python.exe ]]; then PYTHON=backend/.venv/Scripts/python.exe
elif [[ -f backend/.venv/bin/python ]];then PYTHON=backend/.venv/bin/python
else PYTHON=python;fi
"$PYTHON" tests/test_cape_landing_v22.py
# Ensure only scoped landing-page assets enter this commit.
git add frontend/landing.html frontend/shared/landing-v2.css frontend/shared/landing-v2.js \
  frontend/public/images/landing-v2/ \
  tests/test_cape_landing_v22.py docs/CAPE_LANDING_V22_WIDE_SECTIONS.md \
  DEPLOY_CAPE_LANDING_V22_GITBASH.sh
git diff --cached --check
git diff --cached --stat
if git diff --cached --quiet;then
  echo 'No landing page changes to publish.';exit 0
fi
git commit -m 'Expand Cape Ranch Design 02 with full-width feature chapters and platform metrics'
git push origin main
echo 'Cape Ranch landing page v2.2 pushed. Render auto-deploy will be triggered by the commit.'
