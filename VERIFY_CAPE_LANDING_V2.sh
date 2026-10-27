#!/usr/bin/env bash
set -euo pipefail
node --check frontend/shared/landing-v2.js
node --check frontend/shared/app.js
python -m pytest -q tests/test_landing_v2.py
git diff --check
printf '\nLanding V2 checks passed.\n'
