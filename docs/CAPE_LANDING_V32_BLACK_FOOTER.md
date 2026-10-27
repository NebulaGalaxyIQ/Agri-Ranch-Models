# Cape Ranch Public Landing V3.2 — Black Footer

**Scope:** Styling only. Replaces the former green footer with an almost-black, dark-screen theme. The final call-to-action directly above it also uses a near-black overlay for a seamless ending. Maintains light Cape Ranch wordmark and readable footer links, subtle dividers, orange hover states, and keyboard focus. Adds a CSS cache-version change to `v=3.2.0` so browsers do not keep the previous green footer.

**Changed files:** `frontend/shared/landing-v3.css`, `frontend/landing.html` (CSS version only), `tests/test_cape_landing_v31.py` (updated obsolete green-footer assertion). New: `tests/test_cape_landing_v32_footer.py`, this note, and deployment script.

**Not modified:** The FastAPI routes, database, authenticated UI, navigation destinations, account access, image assets, hero, feature cards, responsive breakpoints, and JavaScript.

**Deploy:** extract the ZIP into the Git repository root, then run `bash DEPLOY_CAPE_LANDING_V32_BLACK_FOOTER_GITBASH.sh`. All tests use Python's built-in `unittest`; no pytest installation needed. Render auto-deploy is triggered by a successful push to `main`.
