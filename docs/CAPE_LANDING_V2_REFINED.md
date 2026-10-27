# Cape Ranch — Design 02 refined

This is an additive overlay for the public marketing landing page that is **already installed** in `Agri-Ranch-Models`. It does not modify the FastAPI backend, auth code, database, user accounts, routes, or authenticated frontend.

Changes: authentic Cape Ranch logotype from the brand asset, high-resolution sunset rancher hero with left-side cream overlay, reference-aligned hero typography and spacing, four photographic category tiles, eight hoverable feature cards, reliable sequential scroll-reveal animations, accessible mobile navigation and keyboard/focus states, reduced-motion support, and a subtle scrolling progress indicator.

The landing page uses `/` and retains your sign-in at `/login`, authenticated app at `/app`, and registration at `/register-organization`. The logo and hero are local `.webp` files inside `frontend/public/images/landing-v2/`, so no external photo host is required. The background was generated for this project; any small dashboard visuals are illustrations, not real company metrics.

## Installation and safe publication

1. Make sure your previously installed landing design is already working and your local Git repository has the latest `main`.
2. Extract the overlay ZIP directly into the repository root (`-d .`).
3. Run `bash DEPLOY_CAPE_LANDING_DESIGN02_REFINED_GITBASH.sh` to run tests, stage **only these landing-related files**, commit, and push.
4. Render's auto-deploy on the `cape-ranch-web` service will deploy the commit.
5. Hard-refresh `https://www.caperanch.com` to load the new `?v=2.1.0` scripts and styles plus unique image filename.

If you want to test locally without pushing: `python tests/test_landing_v2_refinement.py`, `node --check frontend/shared/landing-v2.js`.

**Do not re-run the old V2 installer or restore the previous `hero-design02.webp` after applying this overlay.**
