# API contract v1 (design)
Base /api/v1/admin/. JSON, UTF-8, same-origin session and CSRF; ISO 8601 timestamps with offset or UTC, explicit editorial date YYYY-MM-DD. UUID identifiers. Paginated list {count,next,previous,results}. Errors {code,message,fields,request_id}; never raw traces. HTTP 400 validation, 401 or 403 authentication depending on session policy, 403 forbidden, 404 inaccessible object, 409 stale version/transition conflict, 429 throttling. PATCH requires expected version or If-Match; duplicate import/action retry uses idempotency key. Server ignores no protected fields: reject attempts to change actor/status outside authorized commands.

| Resource | Operations |
|---|---|
| auth/session, auth/login, auth/logout | session info, login, logout |
| users, roles | list/create/detail/update; deactivate/revoke actions |
| categories, countries, cities, areas, venues, promoters, sponsors | CRUD with archive rather than delete |
| events, occurrences, occurrences/{id}/prices | list/create/detail/update, archive/restore; recurring preview/commit |
| occurrences/{id}/submit, review, verify, return, reject, cancel | POST transition, reason/evidence as required |
| issues, issues/{id}/events | list/create/update, propose eligible items, include/exclude |
| issues/{id}/cover, picks, grid, features, teasers | GET/PUT ordered editorial content with version guard |
| issues/{id}/readiness, submit-review, approve | readiness GET; transitions POST |
| media | initiate/upload/finalize/list; authorized download |
| imports | upload/dry-run, detail, commit, row report |
| reports/dashboard, reports/events, reports/fees | filtered aggregate GET, authorized exports |
| audit | restricted read-only list/detail |

Example occurrence draft: {"event_id":"<uuid>","venue_id":"<uuid>","editorial_date":"2026-12-11","starts_at":"2026-12-12T00:30:00+03:00","ends_at":"2026-12-12T03:00:00+03:00","price_type":"UNKNOWN","version":1}. Example is synthetic, not source data. Verification endpoint accepts evidence, reason, expected_version; actor derived from session. Issue picks PUT contains ordered [{issue_event_id,rank,why_go,curator_playing}] and expected version; transaction prevents duplicates. Generate OpenAPI in implementation and test schema drift.

Future public /api/v1/public/events, issues/latest, issues/{slug}, venues, categories: only explicitly published allowlisted snapshots, no internal contact, source evidence, fees or draft states. Future MCP uses authenticated scoped API; does not write workbook or DB directly.
