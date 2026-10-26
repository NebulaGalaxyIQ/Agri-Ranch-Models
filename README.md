# Cape Ranch — Modular Agricultural Management

This release replaces the **old source implementation files**, not merely their import paths. The 17 legacy version-named Python implementations have been moved into operational module files. The obsolete V4 application handlers were retired and `backend/main.py` now only assembles the application.

## What is included

- **Animal Fattening:** Ranches, Projects, Batches, Pens, Animals, Weighing, Feeding, Feed Mixes, Animal Sales. Dedicated profile and performance API with date/age/entry weight/current weight/gain/ADG, individually recorded feed, costs by currency, proposed selling value and projected direct contribution.
- **Crop farming, livestock and poultry, gardening, machinery, inventory, Finance, employee tasks, audit, reports, subscriptions, platform administration, Help Center.** Their existing functional APIs have been transferred into module directories. Where a feature has not yet been rewritten as a stand-alone business service it continues to share utilities by explicit cross-module imports.
- **Frontend:** Keep approved V6.5 photographic image assets and CSS, independent full-width module pages, green main sidebar, modal forms and permission-aware staff interface.
- **Security:** Organization membership checks, role permissions, licensing and tenant-filtered records remain enforced by the relevant backend handlers.

## Backend structure

Each module uses a minimal `models.py`, `schemas.py`, `service.py`, `router.py` convention with an `__init__.py` package marker. ORM definitions for feed stock, money entries, crops, livestock, gardening, equipment, subscription and support are located in the modules which own them. Old `v5_`/`v6_` database **table names** are preserved intentionally; renaming live tables without a verified mapping would risk data loss. Old **versioned API URLs** are retained as compatibility endpoints for client integrations. There is only one set of implemented handlers; there are no retired Python source files to import.

## Frontend structure

Individual modules have `frontend/pages/<module>/index.js`, `service.js`, and `style.css`, backed by `frontend/shared/`. Approved photographs remain in `frontend/public/images/v65/` with unchanged paths and contents. The application homepage is `frontend/index.html`.

## Installation

1. Back up your *current project directory AND PostgreSQL database* (`pg_dump` or your managed backup solution). Stop the server.
2. Extract the ZIP **to the parent directory** of `Ranching_Project_2026`, retaining the ZIP's enclosing `Ranching_Project_2026/` folder.
3. From your project root, run `bash INSTALL_MODULAR.sh`. It validates source, backs up matching retired source files under `.upgrade_backups/`, then removes only specifically named obsolete files. This does **not** modify the database or `.env`.
4. Start the app: `cd backend && uvicorn main:app --reload --host 127.0.0.1 --port 8000`. Visit http://127.0.0.1:8000 and press Ctrl+Shift+R.

Existing schema setup uses the historical additive upgrade function. **Test first with a cloned PostgreSQL database**. This release does not provide a formally reversible Alembic migration and is not yet production-certified.

## Validation

Run individual suites separately, because their setup fixtures each expect a fresh platform-owner database:

```bash
PYTHONPATH=backend pytest -q tests/test_animal_profiles_and_offers.py
PYTHONPATH=backend pytest -q tests/test_assigned_mix_policy.py
PYTHONPATH=backend pytest -q tests/test_animal_sales_finance.py
PYTHONPATH=backend pytest -q tests/test_crop_and_livestock_production.py
PYTHONPATH=backend pytest -q tests/test_feed_inventory_audit.py
```

This refactor **does not claim** that every existing calculation, financial allocation, browser screen and database migration has received a full production security audit. Source moved into operational domains can still be simplified further internally. No new data model table replacements are applied automatically.
