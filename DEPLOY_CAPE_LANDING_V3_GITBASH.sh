#!/usr/bin/env bash
# Cape Ranch Design 01 + 03 + 06 combined landing. Safe scoped publisher.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [[ ! -d .git ]]; then echo 'ERROR: Run in the Ranching_Project_2026 Git repository root.' >&2; exit 2; fi
if [[ "$(git branch --show-current)" != 'main' ]]; then echo 'ERROR: Checkout main first.' >&2;exit 2;fi
if ! git diff --cached --quiet; then echo 'ERROR: Other changes are staged; review those first.' >&2;exit 2;fi
for f in frontend/landing.html frontend/shared/landing-v3.css frontend/shared/landing-v3.js tests/test_cape_landing_v3.py;do
  if [[ ! -s "$f" ]];then echo "ERROR: Missing $f. Extract ZIP into repo root." >&2;exit 2;fi
done
# The existing landing installer already configured '/' -> frontend/landing.html.
# Never patch backend/main.py automatically during a public visual upgrade.
if ! grep -Fq "FileResponse(FRONTEND/'landing.html')" backend/main.py && \
   ! grep -Fq 'FileResponse(FRONTEND/"landing.html")' backend/main.py; then
  echo 'ERROR: backend/main.py does not appear to serve frontend/landing.html at /. Stop: do not overwrite backend routes.' >&2;exit 2
fi
if ! grep -Eq "@app.get\(['\"]/(login|app)['\"]" backend/main.py;then
  echo 'ERROR: Login/app route check failed. Do not publish until reviewed.' >&2;exit 2
fi
if [[ -x backend/.venv/Scripts/python.exe ]]; then PYTHON='backend/.venv/Scripts/python.exe'
elif [[ -x backend/.venv/bin/python ]];then PYTHON='backend/.venv/bin/python'
elif command -v python >/dev/null 2>&1; then PYTHON=python
else echo 'ERROR: Python missing.' >&2; exit 2;fi
"$PYTHON" -m unittest discover -s tests -p 'test_cape_landing_v3.py' -v
if command -v node >/dev/null 2>&1; then node --check frontend/shared/landing-v3.js;else echo 'WARNING: Node not installed; skip JS check.';fi

# Retire ONLY superseded landing-v2 files if another frontend page does not
# reference that stylesheet/script. Never delete assets in v65, branding, or
# other modules. Any shared old photo referenced elsewhere is preserved.
remove_known(){
  local f="$1"
  if [[ -f "$f" ]];then
    if git ls-files --error-unmatch "$f" >/dev/null 2>&1;then git rm -q -- "$f";else rm -f -- "$f";fi
    echo "Retired unused landing asset: $f"
  fi
}
if [[ -f frontend/shared/landing-v2.css ]] && ! grep -RlF 'landing-v2.css' frontend --include='*.html' --include='*.js' --exclude='landing-v2.css' >/dev/null 2>&1; then
  remove_known frontend/shared/landing-v2.css
fi
if [[ -f frontend/shared/landing-v2.js ]] && ! grep -RlF 'landing-v2.js' frontend --include='*.html' --include='*.js' --exclude='landing-v2.js' >/dev/null 2>&1; then
  remove_known frontend/shared/landing-v2.js
fi
# Legacy test scripts were scoped to the superseded landing V2 markup.
if [[ ! -f frontend/shared/landing-v2.css && ! -f frontend/shared/landing-v2.js ]]; then
  for oldtest in tests/test_cape_landing_v22.py tests/test_landing_v2_refinement.py tests/test_landing_v2.py;do
    remove_known "$oldtest"
  done
  for file in frontend/public/images/landing-v2/*.webp;do
    [[ -f "$file" ]] || continue
    asset="landing-v2/$(basename "$file")"
    # Ignore archived docs/tests: only actual frontend runtime references count.
    if grep -RlF "$asset" frontend --include='*.html' --include='*.css' --include='*.js' --exclude-dir=landing-v2 >/dev/null 2>&1;then
      echo "PRESERVED: shared image still referenced: $file"
    else remove_known "$file";fi
  done
else
  echo 'Kept legacy image folder: a legacy landing stylesheet or script is still used.'
fi

git add frontend/landing.html frontend/shared/landing-v3.css frontend/shared/landing-v3.js \
  frontend/public/images/landing-v3/ tests/test_cape_landing_v3.py \
  DEPLOY_CAPE_LANDING_V3_GITBASH.sh docs/CAPE_LANDING_V3_IMPLEMENTATION.md

git diff --cached --check
git diff --cached --stat
if git diff --cached --quiet;then echo 'Landing V3 already up to date; nothing to commit.';exit 0;fi

git commit -m 'Build Cape Ranch compact premium Landing V3 with new photography and interactions'
git push origin main
printf '\nSUCCESS: Cape Ranch V3 pushed; Render auto-deploy should begin.\n'
printf 'Public: https://www.caperanch.com/\nApp: https://www.caperanch.com/login\n'
