# Operational workflows
## Event
DRAFT -> SUBMITTED -> UNDER_REVIEW -> VERIFIED or RETURNED or REJECTED. RETURNED -> DRAFT -> SUBMITTED. Rejected reopen requires authorized reason. Verified material edit -> SUBMITTED and new revision; preserve old decision history. Cancellation can occur independently; removes occurrence from future eligibility; already released edition retains snapshot and gets a correction in publishing phase. Archive/restore retain prior status; re-evaluate eligibility. Collectors may edit own/assigned drafts only; verifier cannot verify own submission by default (proposed separation policy; owner may approve alternate controlled process).

Verification requires source and method (venue call, official promoter confirmation, official listing, etc.), actual schedule, location, price state and verifier identity. Missing price can be explicitly UNKNOWN if otherwise verified; never display as free. Missing essential schedule/location stays draft or returned. No invented end date, verification identity or price. Duplicate candidates reviewed by human; do not silently merge.

## Weekly issue
DRAFT -> COLLECTING -> EDITORIAL -> IN_REVIEW -> APPROVED (admin phase readiness only). PUBLISHED/ARCHIVED actual release behavior phase 07. Return to EDITORIAL with reason. Changes affecting approved content invalidate approval; publication requires new review. Default cycle from README: Fri–Mon collection, Monday 17:00 verification, Tuesday picks and editorial, Wednesday review, Thursday 07:00 release. Configurable Kampala local deadlines. Issue date rules: Thu start default, 7 inclusive editorial days; alternative start only explicit authorized policy. Grid day inside issue.

## Final publication gates (phase 07)
At least one eligible verified event; 7 unique picks with descriptions and disclosures; no fictional/mock marker or placeholder content, no missing required assets (optional assets require intentional omission); stale teasers excluded; all blocking layout warnings resolved, excluded events reported; approval bound to immutable content hash. Preview may be incomplete and labeled DRAFT. No force override for release. Fees distinguish recorded charge from actual receipts; payment workflow deferred.

## Grid
Original buckets 17–19, 20–21, 22–23, 00–01, 02–03; 04:00 onward not in legacy grid. Maximum 8 rows, 5 columns. Preserve actual slot; collisions resolved via explicit editorial selection or alternative layout, never moving start time. Full-week list retains eligible events omitted from grid.

## Import
Quarantine -> dry-run -> review -> commit -> reconcile. Source file hash + sheet + row provenance, strict typed parsing, no formula evaluation, reject unsafe formulas in input fields. Preserve legacy ID only as source reference; issue dates/formulas recomputed. Unmapped verifier initials require authorized mapping or unverified status; sample imports isolated. Overnight conversion preview before confirmation, blank price UNKNOWN, conditional free preserved. Existing duplicate keys reported; idempotent commit; transaction rollback on fatal error. No blind overwrite of concurrent edits.
