#!/usr/bin/env bash
# Cape Ranch V3.1 surgical landing-page copy/metric/photo/footer update.
# No backend, database, authentication or unrelated module changes.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
if [[ ! -d .git ]]; then echo 'ERROR: Run from Ranching_Project_2026 Git repository root.' >&2; exit 2; fi
if [[ "$(git branch --show-current)" != 'main' ]]; then echo 'ERROR: Switch to main before publishing.' >&2; exit 2; fi
if ! git diff --cached --quiet; then echo 'ERROR: Other staged changes found. Commit/unstage them first.' >&2; exit 2; fi
for f in frontend/landing.html frontend/shared/landing-v3.css frontend/shared/landing-v3.js \
 tests/test_cape_landing_v31.py frontend/public/images/landing-v3/cape-ranch-footer-logo.webp; do
 if [[ ! -s "$f" ]]; then echo "ERROR: Missing $f. Extract ZIP in the repository root." >&2; exit 2; fi
done
if ! grep -Fq "FileResponse(FRONTEND/'landing.html')" backend/main.py && \
   ! grep -Fq 'FileResponse(FRONTEND/"landing.html")' backend/main.py; then
 echo 'ERROR: Backend does not serve landing.html at root, stop and inspect route.' >&2; exit 2
fi
if ! grep -Eq "@app.get\(['\"]/(login|app)['\"]" backend/main.py; then
 echo 'ERROR: Existing /login or /app route not found. Refusing to deploy.' >&2; exit 2
fi
export PYTHONDONTWRITEBYTECODE=1
if [[ -x backend/.venv/Scripts/python.exe ]]; then PYTHON='backend/.venv/Scripts/python.exe'
elif [[ -x backend/.venv/bin/python ]]; then PYTHON='backend/.venv/bin/python'
else PYTHON=python; fi
"$PYTHON" -m unittest discover -s tests -p 'test_cape_landing_v31.py' -v
if [[ -f tests/test_cape_landing_v3.py ]]; then
 "$PYTHON" -m unittest discover -s tests -p 'test_cape_landing_v3.py' -v
fi
if command -v node >/dev/null 2>&1; then node --check frontend/shared/landing-v3.js; fi

git add -- frontend/landing.html frontend/shared/landing-v3.css \
  frontend/public/images/landing-v3/cape-ranch-footer-logo.webp \
  tests/test_cape_landing_v31.py \
  DEPLOY_CAPE_LANDING_V31_GITBASH.sh \
  docs/CAPE_LANDING_V31_CHANGELOG.md

git diff --cached --check
GIT_PAGER=cat git --no-pager diff --cached --stat
if git diff --cached --quiet;then echo 'Already up-to-date; nothing to commit.';exit 0;fi
git commit -m 'Refine Cape Ranch landing hero copy, metrics and dark footer'
git push origin main
printf '\nSUCCESS: Landing V3.1 published. Render auto-deploy should follow.\n'
printf 'Website: https://www.caperanch.com/\nLogin: https://www.caperanch.com/login\n'
