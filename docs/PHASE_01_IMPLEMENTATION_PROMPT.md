# Implementation work order — Phase 01

You are implementing MUKYAKAZZE, an admin-first production entertainment data collection platform. Read all Phase 00 docs and preserve the original MCP archive separately. Do not implement the public frontend, renderer integration, external promoter portal or ticketing in this phase.

In the owner-designated repository, inspect existing branches, files, dependency/toolchain availability and working-tree state. If none exists, initialize a clean local repository. Do not overwrite unrelated work or push to an unspecified remote. Establish a phase branch and record baseline. Implement the complete Phase 01 foundation in cohesive commits:

- Django + DRF backend, custom user from initial migration, PostgreSQL, secure same-origin session login/logout/current-user and CSRF, group permissions, user activation/revocation, privileged MFA design, minimal append-only audit service, health endpoints. Default deny; no production fixture credentials.
- React TypeScript Tailwind admin shell, login screen, accessible responsive navigation and authorization-aware empty states. Do not invent business metrics. Use the Phase 00 brand tokens. No public Next.js app.
- Docker Compose and environment templates, real PostgreSQL migrations, separate safe production settings, CI commands, locked tested dependencies and images, README runbook. Avoid premature worker/media dependencies if not needed for this phase; document future integration.
- Tests for anonymous, disabled, unauthenticated, privileged and forbidden access, CSRF, session rotation/revocation, direct object access, audit actor, clean database migration, application build and real browser login/navigation. Use real PostgreSQL. Record any tests you cannot run as BLOCKED, not PASS.

Deliver source, test evidence, migration/rollback guidance, exact commit IDs and qualification report. Do not declare Q01 passed unless evidence supports every critical criterion. Do not advance into Phase 02 without recording Q01 status. Owner inputs such as hosting, actual staff, MFA and backup custody may remain production blockers; use safe local development defaults only.
