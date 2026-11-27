# Phase 02A — event categories (candidate)

Source implemented; runtime qualification pending. No public frontend, locations, venues, promoters, sponsors, media or events implemented in this slice.

The eleven labels and colours match the original workbook Lists sheet. Stable codes use uppercase letters, digits and underscores; BUSINESS_NETWORKING maps to BUSINESS & NETWORKING. Only category master data is seeded; no fictional events. Archive/restore is a reversible flag. Codes cannot be changed through the API. All five staff groups can read; Administrator and Editor can write. The provision_roles command reconciles permissions after migration. Writes use the existing audit log and optimistic version checks.

Local development verification:
- docker compose up --build -d
- docker compose logs --tail=60 backend
- docker compose exec backend python manage.py check
- docker compose exec backend python manage.py makemigrations --check --dry-run
- docker compose exec backend pytest -q -p no:cacheprovider
- Open http://localhost:8080, sign in and open Categories. Confirm eleven seeds, create a synthetic category, edit, archive and restore. Check Collector read-only access and audit log.

Existing CI runs on push and PR. Do not merge until review and qualification. Preserve the existing PostgreSQL volume and .env; never use down -v for this upgrade. Runtime, database migration consistency, frontend build and browser checks not yet executed in authoring environment.
