# Delivery roadmap and phase gates
Admin release is the first milestone. No public frontend coding before Q05 acceptance.
| Phase | Work packages | Exit gate |
|---|---|---|
| 00 | source inventory, requirements, mapping, ADR, logical model, workflows, permission/API design, baseline | Q00 design review; current package |
| 01 | repository bootstrap, Docker, PostgreSQL, Django custom user, migrations, session/CSRF, roles, audit core, React shell, CI | Q01 |
| 02 | categories/areas/venues/promoters/sponsors, media storage, upload rights, admin screens | Q02 |
| 03 | event/occurrence/price models, verification services, search, recurrence, overnight handling, browser workflows | Q03 |
| 04 | issue and editorial modules, cover/picks/grid/features/teasers, readiness | Q04 |
| 05 | workbook import/export, reporting, operational security, backup and restore, staging/UAT | Q05 admin go-live |
| 06 | renderer adapter and snapshot contract, HTML/PNG/PDF/caption | Q06 |
| 07 | final approval, versioned release, corrections and distribution | Q07 |
| 08 | responsive public Next.js frontend | Q08 |
| 09 | MCP/AI draft assistance | scoped permission and human review |
| 10 | external promoter/commercial expansion | separate owner acceptance |
| 11 | mobile and other integrations | separate owner acceptance |

## Phase 01 work order (ready to hand to implementation agent)
1. Create new repository or branch from owner-designated baseline. Keep original archive immutable. No remote push without target.
2. Scaffold backend/ (Django, DRF), apps/admin-web/ (React TS Tailwind), infrastructure/, docs/, tests/, packages/ adapter directories; no public web app yet.
3. Qualify compatible supported versions, lock dependencies and container digests. Docker Compose PostgreSQL/backend/admin; secret placeholders; dev/staging settings.
4. Custom user model before first migration; groups/permissions; login/logout/session endpoint, CSRF, activation/revocation, object access default-deny; append-only audit skeleton; privileged MFA design/qualification.
5. Build login and authenticated navigation shell with original branding, no fabricated counts; unauthorized and expired-session states. Add health checks.
6. Run migration from clean PostgreSQL, lint/typecheck, integration and real browser tests; include authorization and concurrent session checks. CI with real database. Record versions, commands/results and gaps; do not advance on failed critical gate.

## Pending owner inputs
Repository/branch location, hosting and DNS, actual staff role assignments, MFA provider, storage and backup custody, privacy/retention and media rights policy, production event source/verification rules. Proposed defaults allow development but production release blocked until validated. Public UI samples beyond magazine templates may be supplied before Phase 08. No external repository or production credentials supplied with archive.
