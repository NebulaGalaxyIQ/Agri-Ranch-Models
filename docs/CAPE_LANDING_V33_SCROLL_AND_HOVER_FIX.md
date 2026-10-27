# Cape Ranch Landing Page V3.3 — Scroll Reveal & Hover Fix

## What broke

In V3.1/V3.2, `landing-v3.js` added `cr3-js`, `cr3-waiting` and `cr3-is-visible`, but `landing-v3.css` had no matching regular-motion reveal declarations. Consequently, the feature sections did not visually enter when scrolled into view. The V3.2 cache URLs continued to reference the older JS asset version.

## What changed

- New CSS styles animate visibility and vertical entrance of below-fold `.cr3-reveal` elements; default HTML remains **visible** if scripts or observers fail.
- The initial hidden state is committed before animations are enabled, preventing fade-out flicker on load.
- Cards animate in page-local staggered order; IntersectionObserver activates them as the visitor scrolls, with a scroll/resize/pageshow/hashchange fallback.
- On finished transitions, the waiting state is removed so CSS card hover transforms remain operational.
- Category image tabs, feature visuals, mini-cards, metrics, FAQ entries, onboarding steps and illustrative dashboard cards have visible hover/focus feedback.
- Users with reduced-motion accessibility settings see all content immediately, with no entrance animation.
- CSS and JS URLs use `v=3.3.0` to prevent the browser from reusing cached V3.2 files.
- **No backend, database, routes, images, login, organization registration or black footer changes.**

## Installation

From Git Bash, in the project root:

```bash
unzip -oq "/c/Users/Hp/Downloads/Cape_Ranch_Landing_V33_Scroll_Reveal_Hover_Fully_Fixed.zip" -d .
bash DEPLOY_CAPE_LANDING_V33_GITBASH.sh
```

The publisher tests with Python standard-library unittest, checks JavaScript with Node, stages only the three landing-page files plus this document, script and tests, then pushes `main` to trigger Render auto-deploy.

## Verification in browser

1. Open https://www.caperanch.com in a **private window** or hard refresh once (`Ctrl+Shift+R`).
2. Scroll slowly past the image tabs into feature chapters: photos and headings should slide up and fade in sequentially, then remain visible.
3. Hover a photo tile, a mini feature card, the image in a chapter, metrics and a FAQ row: each responds visibly.
4. Confirm `/login`, `/register-organization`, and the nearly-black footer still work.
5. In Windows accessibility settings with **Reduce animations** enabled, content remains visible without entrance movement.
