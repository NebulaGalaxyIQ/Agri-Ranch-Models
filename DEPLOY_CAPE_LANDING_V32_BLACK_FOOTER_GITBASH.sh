#!/usr/bin/env bash
# Surgical Cape Ranch landing-page footer color update. No backend edits.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [[ ! -d .git ]]; then echo 'ERROR: Extract in the Ranching_Project_2026 Git repository root.' >&2; exit 2; fi
if [[ "$(git branch --show-current)" != 'main' ]]; then echo 'ERROR: Switch to main.' >&2; exit 2; fi
if ! git diff --cached --quiet; then echo 'ERROR: Other staged changes found; leave them staged separately.' >&2; exit 2; fi
for f in frontend/landing.html frontend/shared/landing-v3.css tests/test_cape_landing_v32_footer.py; do
  if [[ ! -s "$f" ]]; then echo "ERROR: Missing $f" >&2; exit 2; fi
done
if ! grep -Fq 'landing-v3.css?v=3.2.0' frontend/landing.html; then
  echo 'ERROR: Updated CSS version is missing.' >&2; exit 2
fi
if ! grep -Fq '.cr3-footer{background:#080a0c' frontend/shared/landing-v3.css; then
  echo 'ERROR: Black footer rule is missing.' >&2; exit 2
fi
if ! grep -Fq '/login' backend/main.py || ! grep -Fq '/app' backend/main.py; then
  echo 'ERROR: Authentication routes missing from backend/main.py.' >&2; exit 2
fi

export PYTHONDONTWRITEBYTECODE=1
if [[ -x backend/.venv/Scripts/python.exe ]]; then PYTHON='backend/.venv/Scripts/python.exe'
elif [[ -x backend/.venv/bin/python ]]; then PYTHON='backend/.venv/bin/python'
else PYTHON=python; fi
for test in test_cape_landing_v3.py test_cape_landing_v31.py test_cape_landing_v32_footer.py; do
  if [[ -f "tests/$test" ]]; then "$PYTHON" -m unittest discover -s tests -p "$test" -v; fi
done
if command -v node >/dev/null 2>&1; then node --check frontend/shared/landing-v3.js; fi

git add -- frontend/landing.html frontend/shared/landing-v3.css \
  tests/test_cape_landing_v31.py tests/test_cape_landing_v32_footer.py \
  DEPLOY_CAPE_LANDING_V32_BLACK_FOOTER_GITBASH.sh docs/CAPE_LANDING_V32_BLACK_FOOTER.md

git diff --cached --check
GIT_PAGER=cat git --no-pager diff --cached --stat
if git diff --cached --quiet; then echo 'No new changes to publish.'; exit 0; fi
git commit -m 'Set Cape Ranch landing CTA and footer to premium black theme'
git push origin main
printf '\nSUCCESS: V3.2 black footer pushed. Render auto-deploy should start.\n'
printf 'Review: https://www.caperanch.com/\n'
