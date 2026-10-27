# Cape Ranch Landing V3 — 01 + 03 + 06

This release replaces the *public pre-login page only*. The backend, organization registration, account management, `/login`, `/app`, and Neon database are not modified.

## Page design

- Design 01: cinematic rancher hero, authentic Cape Ranch wordmark, restrained editorial typography.
- Design 03: six compact photographic category tabs (134px high desktop; 96px mobile).
- Design 06: four slim platform metrics (product-focused, plus a clearly labelled 1,000+ **future goal**, not an actual customer count).
- Six compact bands alternating cream, forest green, white and pale orange, each with one large image and three 44px mini highlights.
- Illustrative HTML/CSS dashboard (explicit DEMO label, **not** fictional operational data), four setup steps, accessible FAQ, and CTA.
- Progressive one-time IntersectionObserver animations with reduced-motion support, hover accents and mobile dropdown navigation.

## Real assets, not mockup crops

Local folder: `frontend/public/images/landing-v3/`. Hero is the original separately generated high-resolution rancher panorama (1672×941). Eight additional 1800×430 WebP landscape photographs are taken from Cape Ranch's existing V6.5 photographic library, saved with high-quality WebP compression. The genuine Cape Ranch brand mark is included at 485×80 WebP. No upscaled 530px V2 thumbnail is used.

## Deployment

Extract the ZIP into your checked-out `Ranching_Project_2026` repository root, then run:

```bash
bash DEPLOY_CAPE_LANDING_V3_GITBASH.sh
```

It requires the previously installed public route serving `frontend/landing.html` and the existing `/login` route. Uses Python's stdlib `unittest` (no pytest needed), checks JS using Node (if installed), verifies staged whitespace, retires only safely unreferenced legacy landing-V2 assets, commits scoped V3 files, and pushes `main` to trigger Render. It intentionally does not update backend or database files.

If other services/pages reference legacy `landing-v2` assets or script, they will be preserved.

## Preview and smoke tests

After Render is live: verify `/`, `/login`, `/register-organization`, `/app`, and `/api/healthcheck`. Check the public page at 1440px and 390px, move through menu, FAQ accordion, category anchors, and observe a chapter reveal while scrolling. Lighthouse should be run from a normal browser after deployment; this environment's Chromium had policy-blocked navigation.

No current adoption customer counts, user testimonials or fabricated sales records are claimed. Any future real customer-number metrics should come from verified organization data and public-use policy.
