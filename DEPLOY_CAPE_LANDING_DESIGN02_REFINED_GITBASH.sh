#!/usr/bin/env bash
# Cape Ranch / Design 02 enhancement: safely stage ONLY these landing page files.
set -euo pipefail
cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
if [[ ! -d .git || ! -f backend/main.py || ! -f frontend/landing.html ]]; then
  echo 'ERROR: Open this script in the Cape Ranch Git repository root.' >&2; exit 2
fi
if [[ "$(git branch --show-current)" != 'main' ]]; then
  echo 'ERROR: Checkout the main branch before deployment.' >&2; exit 2
fi
if ! git diff --cached --quiet; then
  echo 'ERROR: You have other staged changes. Unstage/review them first; nothing committed.' >&2; exit 2
fi
if ! grep -Fq "FileResponse(FRONTEND/'landing.html')" backend/main.py; then
  echo 'ERROR: The public landing route has not been installed. Existing API untouched.' >&2;exit 2
fi
if ! grep -Fq "@app.get('/login',include_in_schema=False)" backend/main.py; then
  echo 'ERROR: Existing /login route missing. Please review backend/main.py.' >&2;exit 2
fi
if ! command -v node >/dev/null 2>&1;then echo 'ERROR: Node.js is required for JS syntax checks.' >&2;exit 2;fi
node --check frontend/shared/landing-v2.js
if [[ -f frontend/shared/app.js ]]; then node --check frontend/shared/app.js; fi
if [[ -f backend/.venv/Scripts/python.exe ]]; then PYTHON=backend/.venv/Scripts/python.exe
elif [[ -f backend/.venv/bin/python ]]; then PYTHON=backend/.venv/bin/python
else PYTHON=python; fi
"$PYTHON" tests/test_landing_v2_refinement.py
"$PYTHON" -m compileall -q backend/main.py
git diff --check

git add frontend/landing.html frontend/shared/landing-v2.css frontend/shared/landing-v2.js \
  frontend/public/images/landing-v2/hero-design02.webp \
  frontend/public/images/landing-v2/cape-ranch-logo.webp \
  tests/test_landing_v2_refinement.py \
  DEPLOY_CAPE_LANDING_DESIGN02_REFINED_GITBASH.sh \
  docs/CAPE_LANDING_V2_REFINED.md

git diff --cached --check
git diff --cached --stat
if git diff --cached --quiet;then echo 'No new landing-page changes to publish.';exit 0;fi
git commit -m 'Refine Cape Ranch landing Design 02 hero branding and scroll reveal'
git push origin main
printf '\nPushed. Render auto-deploy should start for cape-ranch-web.\n'
