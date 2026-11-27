# MUKYAKAZZE platform — Phase 01 candidate
Admin-first modular monolith. **PARTIAL / NOT PRODUCTION QUALIFIED.** No public frontend, no sample events seeded, no data collection modules yet. Original upload is unchanged and remains separate; its checksum is in `reference/SHA256SUMS`. Keep the original archive beside the repository if you want to run `sha256sum -c reference/SHA256SUMS` from the repository root. Approved Phase 00 specs in `docs/`.

## Local startup (Docker required; not executed in the authoring environment)
1. Copy `.env.example` to `.env`. Replace both placeholders with independently generated secrets (`python -c "import secrets; print(secrets.token_urlsafe(64))"`). Keep DEBUG=1 only for loopback development. Never commit .env.
2. `docker compose up --build -d` and `docker compose logs backend`. Confirm migrations succeeded.
3. `docker compose exec backend python manage.py createsuperuser` — enter your own email/password interactively; no default password. This recovery account is protected from API changes. Use it to create a regular Administrator in the admin UI.
4. Open http://localhost:8080. Health checks: `/health/live/` and `/health/ready/`.
5. `docker compose exec backend pytest -q` only against a disposable database environment, never production. PostgreSQL test database creation rights required. `docker compose exec backend python manage.py makemigrations --check --dry-run`.
6. To run real browser tests, on host `cd apps/admin-web && npm install && npx playwright install chromium`; provide `E2E_EMAIL`, `E2E_PASSWORD` for a disposable admin account, then `npm run test:e2e`. Never use real production credentials.

## Qualification and rollback
Read `docs/PHASE_01_QUALIFICATION.md`. Migration rollback on disposable DB only: `python manage.py migrate accounts 0001` removes audit trigger; reversing initial user migration can destroy accounts and related data. For deployed recovery, take verified backups, stop writers and restore matching app/DB version rather than destructive down-migration. Docker volume persists across normal `down`; `down -v` destroys local database.

## Security and scope
Same-origin sessions and CSRF, DB-backed role checks, password hashing, session version revocation, login limits and append-only audit trigger are candidates requiring runtime verification. Reverse proxy IP handling needs trusted-proxy policy: current backend sees proxy address, so IP limit is shared behind Nginx. Production requires privileged MFA, secure onboarding/reset, trusted HTTPS configuration, non-development WSGI server, pinned dependency locks/images, least privilege DB roles, monitoring, backup restore and security review. Do not expose this development compose publicly. Public frontend, catalog/events, editorial and rendering integration are later phases. No remote Git repository created or pushed.
