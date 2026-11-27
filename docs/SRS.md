# MUKYAKAZZE — Software requirements v1.0
Status: Phase 00 design baseline; architecture direction accepted in chat; detailed business policies proposed for validation. Admin-first. Public website is out of the initial release.

## Scope and actors
Internal collectors, verifiers, editors, publishers and administrators use an authenticated responsive web app. A PostgreSQL database replaces Excel as operational authority. Existing publication engine remains a reference, not a second writable datastore. External promoter accounts, ticket payments, native app, public browsing and AI automation are deferred. Internal promoter and sponsor records are included.

## Functional requirements
| ID | Requirement | Acceptance |
|---|---|---|
| FR-01 | Authenticated accounts, roles, activation and session revocation | disabled account cannot use existing session; unauthorized requests denied |
| FR-02 | Category, location, venue and promoter management | active records selectable; inactive records preserve history; eleven categories seeded |
| FR-03 | Event drafts and occurrences, pricing, contacts, source, notes, media | required fields enforced on submission/verification, nullable drafts retained |
| FR-04 | Verification, return, reject, cancel, archive, restore | actor, reason, timestamp and version retained; invalid transitions rejected |
| FR-05 | Recurring events and explicit overnight dates | individual occurrences separately verifiable; preview recurrence before save |
| FR-06 | Weekly issues, cover, byline, picks, grid, features, sponsor, upcoming teasers | all original workbook inputs covered; no duplicate ranks; layout warnings shown |
| FR-07 | Excel preview/import/export | formula cells never executed; idempotent commit, row-level errors and provenance |
| FR-08 | Dashboard and filters | totals agree with database for issue, category, status; fees labeled recorded not received |
| FR-09 | Media management | authorized uploads; MIME/signature/size checks; private assets cannot leak |
| FR-10 | Audit and concurrency | sensitive mutations audited; stale version rejected; transactional integrity |
| FR-11 | Editorial readiness | distinguish draft completeness, verification, and final publication eligibility |
| FR-12 | Future publication contract | versioned snapshot schema can reproduce all source templates; renderer integration deferred |
| FR-13 | Help and settings | document operational weekly cycle, timezone, deadlines and contact labels |

## Non-functional acceptance targets (proposed; measure on agreed staging profile)
20 concurrent authenticated staff; 50,000 occurrences; p95 <= 500 ms for ordinary indexed list/detail requests excluding media/imports; p95 <= 1 s for ordinary writes; paginated results default 25 max 100. Responsive from 360px; keyboard navigation and WCAG 2.2 AA target. HTTPS, secure cookies, CSRF, least privilege, dependency scanning, structured redacted logs. Backup target RPO 24h, RTO 4h subject to hosting approval; restore drill mandatory. No production fixture data. Owner must confirm retention, privacy notice, operational contacts, hosting and capacity targets before go-live.

## Release boundaries
Admin release: FR-01–11 and FR-13 operational; FR-12 schema only. Publication generation and actual approval-to-public release in phases 06–07. Public frontend phase 08. No direct public access to draft or internal data.
