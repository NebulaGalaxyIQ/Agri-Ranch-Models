# Cape Ranch Gardening V2.0 — Release notes

**Target repository:** `NebulaGalaxyIQ/Agri-Ranch-Models` (`main`), Cape Ranch.

## What changes

Only the Gardening domain, its frontend view/services/styles, seven additive PostgreSQL tables, gallery pictures for the additional existing-card positions, and a focused integration test. The approved V6.5 global design, shared CSS/JS, public-folder organization, backend application entrypoint, and older V6 tables/APIs are untouched.

### UI work areas (11)

- Dashboard — organization-scoped figures, water litres, garden surface, plants, due/completed tasks, health, expenses grouped by **currency** (no fictional conversions), historical trends.
- Garden areas — existing V6 area registration and bounded updates.
- Plant registry — category, variety, counts, acquisition cost, health/condition, grouped and individual plants.
- Planting & nursery — seeds, germination, survival and nursery status updates.
- Watering & irrigation — **multiple shifts per day**, litres, hours, covered area, date and expense.
- Maintenance & landscaping — planting, weeding, pruning, mowing, mulching, trimming/landscaping and other records.
- Plant health — problems, severity, treatments, follow-up and status changes.
- Routines & tasks — gardening-specific recurrence and supervisor-assigned work; due and overdue indicators; one completion per schedule/day.
- Supplies & costs — cost records linked optionally to existing inventory items, no implicit stock movement, per-currency summaries.
- Inspections — 1–5 scores across four garden criteria, corrective actions and follow-up.
- Analytics & reports — live per-month activities, litres, costs, condition, and XLSX/PDF/CSV downloads.

### Backwards compatibility

Existing `/api/v6/gardening/areas` and `/api/v6/gardening/records` are **unchanged**. Old records appear as historical activity in Gardening V2. New endpoints use `/api/v6/gardening/v2/`. Original `v6_garden_areas` and `v6_garden_records` tables are preserved. The seven new `v11_garden_*` tables are additive.

### Security and data integrity

Every V2 operation uses the established organization context and module-permission checks, and checks that referenced areas/plants/items belong to the requesting organization. Assignment requires active membership in the organization. Routine completion validates due dates and prevents duplicate execution for a given schedule/day at the database layer. Activities can still legitimately have morning, afternoon and evening records in the same area/day. Costs are kept separate by currency. Excel/CSV output sanitizes formula-like strings.

### Deliberate boundaries / not implemented

- The historic **central V5 animal Routine** entity requires batch/animal/pen links; it cannot safely represent garden-area tasks. V2 therefore has **garden-specific routines**. A later, designed cross-module Routine architecture can unify the two without changing animal task validations.
- Adding garden expense entries with an inventory reference **does not issue inventory stock** automatically. Real inventory issues should use the central Inventory workflow, preventing fabricated or duplicate movements.
- No new photo uploads are enabled until private persistent object storage is configured. Existing approved imagery remains unchanged.
- New garden expenses are tracked within Gardening and its reports, **not duplicated in the main Finance ledger**. A dedicated, idempotent cross-module journal connector remains a separate integration.
- Reporting exports show all summary totals but cap each detailed sheet at 500 newest rows (for bounded response sizes).
- No automatic weather/IoT integration or crop sales duplication.
- This package adds automated API integration coverage but is **not a production security certification or a full visual browser QA**.

## Validation commands

Run tests separately: the project's older test suites create global singleton test databases.

```bash
PYTHONPATH=backend pytest -q tests/test_gardening_v2.py
PYTHONPATH=backend pytest -q tests/test_operational_modules.py
node --check frontend/pages/gardening/index.js
node --check frontend/pages/gardening/service.js
```

Local status before packaging: both test suites pass independently, and JS files pass syntax validation.

## Database rollout

1. Back up the Neon production branch and preserve the original local verified dump.
2. Use the Neon **test branch** `cape-ranch-render-smoke-test` first. The application startup `Base.metadata.create_all()` creates additive V2 tables in that branch. The included `GARDENING_V2_ADDITIVE_MIGRATION.sql` is an optional, explicit transactional DDL alternative for a change-controlled release; don't run both needlessly.
3. Verify the new tables and exact restored legacy records on the test branch, including signup/login, authorized staff flows, data isolation and report exports.
4. Release application code to GitHub after review; your Render frontend and backend services have GitHub auto-deploy enabled.
5. Only after testing and reviewing migrations, promote the change to the Neon production branch and switch `DATABASE_URL` appropriately (without pasting credentials in chat or committing them).

## Installation on the user's Windows Git Bash repository

The ZIP is an **overlay patch**, not a full repository replacement. It uses the existing current Git checkout as its base.

```bash
cd "/c/Users/Hp/Desktop/Ranching_Project_2026"
git pull --ff-only origin main
unzip -oq "/c/Users/Hp/Downloads/Cape_Ranch_Gardening_V2_Complete_Patch.zip" -d .
PYTHONPATH=backend pytest -q tests/test_gardening_v2.py
PYTHONPATH=backend pytest -q tests/test_operational_modules.py
node --check frontend/pages/gardening/index.js
node --check frontend/pages/gardening/service.js
git diff --check
git status --short
```

After review, commit and push the targeted paths:

```bash
git add backend/modules/gardening frontend/pages/gardening frontend/public/images/v65/gardening docs/GARDENING_V2_* tests/test_gardening_v2.py
git commit -m "Implement Cape Ranch Gardening V2 operations and reporting"
git push origin main
```

**Deployment limitation:** This package alone is not a GitHub commit and does not trigger Render. If the ChatGPT GitHub integration is disconnected, commit/push using the above commands from Git Bash. If the backend is connected to the Neon *production* branch, do not push without first having a tested schema rollout plan.

**Application URLs:** Full frontend+backend: `https://cape-ranch-api.onrender.com/`. Static frontend at `https://cape-ranch.onrender.com/` does not automatically proxy `/api`; without a same-origin proxy the data-driven pages require the FastAPI-served URL.
