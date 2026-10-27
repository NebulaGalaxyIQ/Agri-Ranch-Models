# Cape Ranch public landing page — Design 02 v2.2

This is a **frontend-only additive update** of the existing Cape Ranch pre-login marketing page. It does not change FastAPI routes, login, permissions, subscription checks, Neon, or any staff workflow. The code expects the earlier landing-page installation (`GET /` -> `landing.html`, `GET /login` -> authenticated shell) to have been applied.

## What's new

- A four-item metrics strip immediately beneath the photographic solution tiles.
- Six full-width, alternating editorial feature chapters: cream / green / white / orange / cream / green.
- Three explanatory mini-cards per chapter (18 total), with elegant hover lift/highlight and staggered on-scroll entrance.
- Features cover livestock, daily routines, crop/garden management, supplies and costs, machinery/projects, and teams/reports.
- Each section includes a locally served photo and two clear navigation actions.
- Responsive desktop/tablet/phone styling, keyboard focus, `prefers-reduced-motion` compliance, lazy loading and images with alt text.
- Continued use of the proper local Cape Ranch logo and sunset rancher hero image.

## Important truthfulness note

The `1,000+` metric is explicitly labeled **"Organizations: our goal"** and described as a **long-term adoption ambition, not a current customer count**. Do not replace this text with "used by 1,000+ organizations" until the number is confirmed by company records. Other displayed metrics describe architectural features (10+ connected management areas, one workspace, 360° view) rather than customer adoption.

## Installing and publishing

Extract the package into the existing local Git checkout and run:

```bash
cd "/c/Users/Hp/Desktop/Ranching_Project_2026"
git pull --ff-only origin main
unzip -oq "/c/Users/Hp/Downloads/Cape_Ranch_Design_02_Wide_Features_Metrics_V22.zip" -d .
bash DEPLOY_CAPE_LANDING_V22_GITBASH.sh
```

The script does not require pytest. It uses the active project's Python interpreter for its standalone checks and commits **only** the landing-page files listed above. On successful push, the configured Render web service automatically redeploys from `main`. The public domain is `https://www.caperanch.com`.

For manual pre-push validation:

```bash
python tests/test_cape_landing_v22.py
node --check frontend/shared/landing-v2.js
git diff --check
```

## Notes

This package intentionally includes all of the previous Design 02 photographic assets (under `frontend/public/images/landing-v2/`) so it can restore any missing photographs and icons. No external image URLs or hotlinked images are required. The dashboard pictured in the page remains illustrative, not live user metrics.
