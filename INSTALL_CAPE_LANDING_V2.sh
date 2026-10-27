#!/usr/bin/env bash
# Run at the root of a checked-out Agri-Ranch-Models repository after extracting this package.
set -euo pipefail
if [[ ! -f backend/main.py || ! -f frontend/index.html || ! -f frontend/shared/app.js ]]; then
  echo 'ERROR: Run from the Cape Ranch repository root (with backend/main.py and frontend/index.html).' >&2
  exit 2
fi
if [[ ! -f frontend/landing.html || ! -f frontend/shared/landing-v2.css || ! -f frontend/shared/landing-v2.js ]]; then
  echo 'ERROR: Unzip the complete landing package into the repository root first.' >&2
  exit 2
fi
python - <<'PY'
from pathlib import Path
import re
p=Path('backend/main.py')
s=p.read_text(encoding='utf-8')
if 'def homepage()' not in s:
    raise SystemExit('Cannot find FastAPI homepage route. Leave original unchanged; check backend/main.py.')
# Only change root FileResponse: do not overwrite main.py or modify any API imports/routers.
pattern=r'(?P<head>@app\.get\([\'\"]/[\'\"]\s*,\s*include_in_schema=False\)\s*\ndef homepage\(\):\s*\n\s*return FileResponse\(FRONTEND\s*/\s*)(?P<quote>[\'\"])(?P<file>index\.html|landing\.html)(?P=quote)(?P<tail>\))'
found=list(re.finditer(pattern,s))
if len(found)!=1:
    raise SystemExit(f'Expected exactly one GET / homepage route, found {len(found)}; backend/main.py NOT changed.')
m=found[0]
s=s[:m.start()]+m.group('head')+m.group('quote')+'landing.html'+m.group('quote')+m.group('tail')+s[m.end():]
if "@app.get('/app',include_in_schema=False)" not in s:
    addition=("\n\n# Cape Ranch public landing: authenticated UI is retained at /app and /login.\n"
              "@app.get('/app',include_in_schema=False)\n"
              "@app.get('/login',include_in_schema=False)\n"
              "def cape_ranch_application_page():\n"
              "    return FileResponse(FRONTEND/'index.html')\n")
    s=s.rstrip()+addition
p.write_text(s,encoding='utf-8',newline='\n')
print('OK: backend/main.py now serves landing.html on / and the existing app shell on /app and /login.')

# Honor existing direct registration/recovery URLs if the current app implementation
# lacks a pathname initializer; this does NOT replace any login or registration forms.
p=Path('frontend/shared/app.js'); s=p.read_text(encoding='utf-8')
marker='/* CAPE_LANDING_V2_DEEP_LINKS */'
if marker not in s:
    pat=r'(function\s+loginPage\s*\(\s*view\s*=\s*[\'\"]login[\'\"]\s*\)\s*\{)'
    matches=list(re.finditer(pat,s))
    if len(matches)==1:
        h=matches[0]
        snippet=("\n " + marker + "\n"
                " if(view==='login' && !window.__capeLandingDeepLinkUsed) {\n"
                "   window.__capeLandingDeepLinkUsed=true;\n"
                "   if(location.pathname==='/register-organization') view='register';\n"
                "   if(location.pathname==='/staff-recovery') view='reset';\n"
                "   if(location.pathname==='/first-time-setup') view='setup';\n"
                " }\n")
        s=s[:h.end()]+snippet+s[h.end():]
        p.write_text(s,encoding='utf-8',newline='\n')
        print('OK: existing auth forms now open directly on their dedicated URLs.')
    else:
        print('NOTICE: App loginPage function uses a different layout; deep links were not modified. Existing auth still intact.')
else: print('OK: auth deep-link patch already installed.')
PY
python -m compileall -q backend/main.py
node --check frontend/shared/landing-v2.js
node --check frontend/shared/app.js
printf '\nCape Ranch Landing V2 successfully installed.\n'
