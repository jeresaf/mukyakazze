# Phase 01 qualification — PARTIAL (Q01 BLOCKED)

Source candidate prepared; no deploy or remote repository configured. Do not advance the formal release gate until tests and security checks are complete.

| Check | Result |
|---|---|
| Python source compileall | PASS (syntax only) |
| Original archive SHA-256 | PASS (copy matched original, verified before packaging; original remains separate) |
| JSON and YAML parsing | PASS (syntax only) |
| Django installation | BLOCKED: package source unavailable |
| Django checks and migration drift | BLOCKED: dependencies absent |
| PostgreSQL migrations and 7 backend test cases | BLOCKED: PostgreSQL and Django absent |
| Frontend dependency install | BLOCKED: offline npm cache missing dependencies |
| TypeScript / React production build | BLOCKED |
| Real browser login/navigation | BLOCKED |
| Docker build, compose startup and rollback | BLOCKED: Docker absent |
| Full security, recovery and deployment | BLOCKED |

## Remaining before Q01
- Install and qualify dependencies, generate transitive lockfiles and pin image digests. The direct pins and image tags are candidate selections only.
- Run CI, PostgreSQL migrations and real browser tests. Check admin access, CSRF, role revocation, database audit protection, concurrency, proxy handling, login abuse, mobile layout and accessibility. Fix any failures.
- Finish OpenAPI/error request IDs, MFA and account recovery/onboarding design, operational audit retention and database roles. Audit trigger prevents normal row updates/deletes, not privileged tampering or truncate. Add trusted proxy handling and test effective rate limits. Current rate limit uses remote socket address; behind Nginx this groups clients.
- Production deploy must use a qualified WSGI server, TLS, restricted network and least privilege credentials; development runserver and local compose are not production architecture.
- Obtain owner decisions on hosting, actual staff, MFA enrolment and backup custody. No production credentials or sample events seeded.

## Scope
Phase 01 contains authentication, staff administration, role permission checks, audit and UI shell. Event collection and editorial screens are explicitly planned, not implemented. No public website is included. Phase 00 specifications remain the baseline; original upload remains unchanged. See README for startup, test and rollback instructions.
