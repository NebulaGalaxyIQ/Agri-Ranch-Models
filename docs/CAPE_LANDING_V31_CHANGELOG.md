# Cape Ranch — Landing V3.1

This is a **surgical frontend-only** update to the installed V3 public landing page. Apply it only after the original V3 is installed. No backend routes, authenticated interfaces or Neon PostgreSQL tables are edited.

## Visible changes

- Hero headline explicitly names ranching, crop farming, animal fattening and other farming models.
- Hero copy now emphasizes eliminating scattered records, managing operations/costs and acting on reliable records.
- The weak `1 Unified workspace` metric becomes `50+ Trackable data fields` with a concrete records-based description; this is a product-capability illustration, **not** an adoption claim.
- Removes all six numerical labels printed on feature photographs without removing the photograph or text beside it.
- Rebuilds the footer with deep forest-green colors and a transparent light Cape Ranch brand mark so the logo remains legible.
- Increments the CSS and JS cache query to `3.1.0` to avoid stale browser assets.

## Deployment

From the repo root, extract the ZIP, then run:

```bash
bash DEPLOY_CAPE_LANDING_V31_GITBASH.sh
```

The shell script uses Python unittest (no pytest installation required) and keeps Git diff output out of pagers.
