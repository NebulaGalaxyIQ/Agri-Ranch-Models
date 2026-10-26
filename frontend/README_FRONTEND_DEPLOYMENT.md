# Cape Ranch — Local Frontend & Deployment Build

This is an **additive tooling upgrade** for the existing browser-native ES modules. It does not replace the working frontend pages, artwork or CSS, change API endpoints or modify PostgreSQL. It avoids the risk of trying to bundle variable-path imports like `/frontend/pages/${module}/index.js`.

## Prerequisites

- Node.js 22.12+ or 20.19+ (the project requires `>=20.19.0`); npm.
- Existing FastAPI backend running on http://127.0.0.1:8000, using the organization's existing PostgreSQL database.
- Backup the project and database before any production change.

## Git Bash / Windows — backend (terminal one)

```bash
cd "/c/Users/Hp/Desktop/Ranching_Project_2026/backend"
# Activate whichever virtual environment exists in your local project.
# Example if it is in the project root:
source ../.venv/Scripts/activate
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

If your virtual environment has a different location, adjust the `source` line.
Check http://127.0.0.1:8000/api/healthcheck .

## Git Bash / Windows — frontend (terminal two)

```bash
cd "/c/Users/Hp/Desktop/Ranching_Project_2026/frontend"
node --version
npm --version
npm install
npm run check
npm run dev
```

Open **http://localhost:3000** (if the browser cannot reach `localhost`, try http://127.0.0.1:3000).
The frontend proxies `/api/*` to the backend, so session cookies and relative API calls remain same-origin at the browser.

`npm run dev:lite` starts a dependency-free local server if you need a temporary alternative to Vite. Refresh after edits in lite mode.

## Production build and test

```bash
cd "/c/Users/Hp/Desktop/Ranching_Project_2026/frontend"
npm run verify
npm run preview
```

Open http://127.0.0.1:4173 . The build is stored in `frontend/dist/`, including `dist/index.html` and `dist/frontend/{shared,pages,public}/`.

**Why no `vite build`?** The existing app uses dynamic imports with absolute `/frontend/` URLs and needs its full directory tree. A controlled copy build preserves those names so that no new runtime asset resolution bugs are introduced. Vite provides local development and HMR; its native asset bundling is deliberately not used for the production output until the application is deliberately refactored to static import maps.

The preview command uses Node only; it is not a public production web server. For production deploy `dist/` to Nginx or a static host that can reverse proxy `/api` to FastAPI on the **same public origin**. A starter Nginx file is included at `frontend/deployment/nginx.example.conf`.

## Configuring ports

Copy `.env.local.example` to `.env.local` and set `CAPE_RANCH_API_TARGET`, `CAPE_RANCH_FRONTEND_PORT` or `CAPE_RANCH_FRONTEND_HOST` as needed. **Do not put database passwords, session secrets or API credentials in frontend files.** `.env.local` must remain uncommitted.

## Deployment readiness checks

- Frontend modules and their media load on the local server.
- Login/logout and session persistence work through the `/api` proxy.
- Verify reports exports, upload workflows, animal/crop modules, image galleries and protected screens.
- Test on Chrome/Edge and narrow screens.
- Configure PostgreSQL backups, TLS, secure session cookies, domain names, reverse proxy limits and log retention.
- Run backend tests and database migrations against a staging database.
- Generate `package-lock.json` with the first `npm install`, commit it to version control and use `npm ci` on later deployments.

This installation only prepares the frontend layer; public production deployment of the backend, database, DNS and TLS is a separate operation.
