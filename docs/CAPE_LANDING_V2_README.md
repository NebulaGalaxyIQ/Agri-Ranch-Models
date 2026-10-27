# Cape Ranch — Public Landing V2 (Design 02)

A standalone, responsive public marketing page at `/`, based on the approved second concept. Login remains the existing application at `/login` or `/app`. Existing organization registration, staff recovery and first-time setup routes continue using the existing application shell. Protected API routes, subscription and tenant isolation, backend operational modules and historic tables are unchanged.

## Contents

- `frontend/landing.html` — full public landing markup and page SEO.
- `frontend/shared/landing-v2.css` — isolated component styles; mobile/tablet/desktop.
- `frontend/shared/landing-v2.js` — mobile menu, overview dialog, optional auth redirect, animations.
- `frontend/public/images/landing-v2/*.webp` — 14 professionally compressed photographic images copied/adapted from the application's existing V6.5 licensed assets to retain consistency.
- `INSTALL_CAPE_LANDING_V2.sh` — idempotent surgical route installer (edits exactly the homepage route and adds `/app` + `/login` routes; preserves all other backend routes).
- `tests/test_landing_v2.py` — static smoke checks; does not need production DB.

## Installation from ZIP

1. Ensure local repository is on latest main and free of unrelated uncommitted changes. Extract ZIP at repository root.
2. Run `bash INSTALL_CAPE_LANDING_V2.sh`.
3. Run `python -m pytest -q tests/test_landing_v2.py` and `node --check frontend/shared/landing-v2.js`.
4. Test locally on a disposable development DB and verify root `/` displays landing, `/login` displays existing login, `/register-organization` shows existing registration form, `/api/healthcheck` responds.
5. Commit only the landing-related files, `backend/main.py`, the small auth change `frontend/shared/app.js`, and test.
6. Push to `main` (auto-deploy on Render); verify health and login.

## Design and behavior

The page uses full-width scenic header, four photographic category tiles, eight interactive feature rows, CSS product mockup, operating workflow section, audience roles, FAQs, and an orange CTA. All feature links are real registration links or internal anchors. The overview button opens a real dialog instead of linking to an unavailable video. No fabricated performance metrics, endorsements, customer counts, or prices are used. Dashboard preview explicitly says illustrative rather than real user data.

The public landing checks `/api/auth/me` for an existing signed-in session and redirects that user to `/app`. Guests remain on `/`. Login and app shell load the original `frontend/index.html`, so existing access control and paths are preserved. A few deep-link guards for registration and password recovery are inserted in `frontend/shared/app.js` if the file contains the expected login handler.

## Deployment caveats

The Render custom domain should point to the **FastAPI web service** (not an independent static site) because the shell calls same-origin `/api` routes. This update performs NO database/schema modification and doesn't set, expose, or change credentials. Existing registered users should continue to authenticate normally. Avoid opening public registration until Neon production branch and organization licensing have been checked.
