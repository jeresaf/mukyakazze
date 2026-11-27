# Verification and qualification
| Gate | Evidence required |
|---|---|
| Q00 reference | archive digest, source parser/validation, field coverage, template inventory, HTML fragments, known limitations |
| Q01 foundation | clean install/migrate on PostgreSQL, login/logout/CSRF, role deny/allow, session revocation, responsive shell, CI |
| Q02 catalog/media | category seeds exact, duplicate handling, invalid colors/coordinates, file spoof/size/path tests, restricted downloads |
| Q03 events | CRUD, every transition, ownership, unauthorized writes, concurrent version conflicts, overnight/recurrence, price states |
| Q04 editorial | issue date and rank uniqueness, invalidation, grid conflict reporting, teasers, feature/cover constraints |
| Q05 admin | all worksheet mapping, import replay/rollback, report totals, browser E2E desktop/mobile, performance, security, restore drill, UAT |
| Q06 renderer | Chromium PNG/PDF pages, fonts/assets, no overflow, semantic parity, immutable builds, failure handling |
| Q07 publication | approval hash, deny mock/stale/draft release, artifact retrieval, revision/correction, rollback |
| Q08 public | allowlisted data, no private fields, accessibility, responsive design, SEO, caching and invalidation |

Regression fixture: 51 total, 31 verified, 19 submitted, 1 rejected, 7 picks, two paid features totaling UGX 400000, 0 legacy errors/5 warnings/2 info; six HTML page fragments expected. Assert seven blank prices remain unknown, four after-midnight rows map by explicit editorial rule, four past teasers flagged, instruction row not category. Legacy eligibility counts are reference only: production migration may downgrade historical unverifiable statuses; reconcile differences, never manufacture approvals. Test xlsx formulas, malformed values, repeated import, conflict rollback, no PII in exports or logs, race on pick rank, edited verification invalidation, malicious uploads, expired sessions. Synthetic fixture never deployed.

Qualification requires real PostgreSQL, actual browser and tested backup restoration, not SQLite-only or screenshots. Security target includes CSRF, XSS, IDOR, SSRF, file traversal, formula injection, dependency vulnerabilities, authentication abuse. Performance workload targets in SRS; record environment and measurements. No production qualification executed at Phase 00.
