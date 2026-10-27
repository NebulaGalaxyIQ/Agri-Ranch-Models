#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f frontend/landing.html || ! -f frontend/shared/landing-v3.js || ! -f frontend/shared/landing-v3.css ]]; then
  echo "ERROR: Missing landing page files. Extract the V3.3 ZIP to the project root first."
  exit 1
fi

echo "=== Cape Ranch V3.3 public landing-page checks ==="
python -m unittest discover -s tests -p 'test_cape_landing_v3.py' -v
python -m unittest discover -s tests -p 'test_cape_landing_v31.py' -v
python -m unittest discover -s tests -p 'test_cape_landing_v32_footer.py' -v
python -m unittest discover -s tests -p 'test_cape_landing_v33_interactions.py' -v
node --check frontend/shared/landing-v3.js
if [[ -f frontend/shared/app.js ]]; then node --check frontend/shared/app.js; fi

echo "=== Stage only V3.3 landing-page updates ==="
# Do not commit unrelated pre-staged work from an earlier task.
while IFS= read -r pre_staged; do
  case "$pre_staged" in
    frontend/landing.html|frontend/shared/landing-v3.css|frontend/shared/landing-v3.js|tests/test_cape_landing_v31.py|tests/test_cape_landing_v32_footer.py|tests/test_cape_landing_v33_interactions.py|docs/CAPE_LANDING_V33_SCROLL_AND_HOVER_FIX.md|DEPLOY_CAPE_LANDING_V33_GITBASH.sh) ;;
    *) echo "ERROR: Unrelated staged file: $pre_staged. Unstage it before running this publisher."; exit 1 ;;
  esac
done < <(git diff --cached --name-only)

git add -- \
  frontend/landing.html \
  frontend/shared/landing-v3.css \
  frontend/shared/landing-v3.js \
  tests/test_cape_landing_v31.py \
  tests/test_cape_landing_v32_footer.py \
  tests/test_cape_landing_v33_interactions.py \
  docs/CAPE_LANDING_V33_SCROLL_AND_HOVER_FIX.md \
  DEPLOY_CAPE_LANDING_V33_GITBASH.sh

git diff --cached --check
GIT_PAGER=cat git --no-pager diff --cached --stat
if git diff --cached --quiet; then
  echo "No new changes to commit. Checking remote push status..."
else
  git commit -m "Fix Cape Ranch V3.3 feature scroll reveals and card hover animations"
fi

git push origin main
echo "SUCCESS: Cape Ranch V3.3 uploaded to GitHub; Render auto-deploy should start."
