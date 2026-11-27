# Phase 03A — event collection and core review candidate

This patch introduces working source for one event + one occurrence + one General price tier per capture, with persistent UUIDs, a paginated event directory, search, editorial dates, Kampala actual timestamps, active catalog references, a single poster link, source and notes. It includes draft editing, submission, review, return, rejection, verification, controlled reopen and cancellation/restoration. Review requires a reason, verification also requires method and evidence, and self-review by creator or submitter is denied. Admin/editor can manage all records; collector owns their own; verifier can see own records and non-draft records for review; publisher cannot see unapproved events. The verification history has an append-only database trigger and the existing audit log records action names and versions. No live event is seeded. The existing database and .env remain intact.

Decisions: a draft requires a title, not the full schedule. Submission requires title/category/venue/editorial date/actual start/source. Unknown pricing is nullable, free is explicitly zero, paid is positive, conditional free is nullable with note required on submit. Prior editorial date is allowed only for actual starts before 06:00 Kampala time; this cutoff is proposed and must be confirmed before production. Exact case-insensitive title+venue+actual-start duplicates are blocked, not merged. Reopening is required before material edits to submitted/verified records; restoration returns an event to draft for reverification. Directory advisory lock serializes writes and parent checks; selected categories and posters are row-locked during mutation. Archive of master-data references after event approval remains a later eligibility/coordination concern. No destructive delete endpoint. Internal source/notes and decisions are visible within the event role scope, never public.

Limitations: recurring event generation, multi-tier pricing UI/API, assignments, event archive/restore separate from cancellation, bulk imports, additional media, rights/consent and storage migration, full issue linkage and approval invalidation are follow-on work. No public website or publishing changes. Full browser testing, unsaved changes guards on navigation, pagination race checks, performance, privacy review and production security qualification remain required. The event data schema is designed for future multiple occurrences and tiers, but they cannot be created through this slice yet. The event list is not optimized for very large datasets. Evidence may contain private information: use only authorized internal references.

Local validation on disposable development DB only:

- `docker compose up --build -d`
- `docker compose logs --tail=60 backend`
- `docker compose exec backend python manage.py check`
- `docker compose exec backend python manage.py makemigrations --check --dry-run`
- `docker compose exec backend pytest -q -p no:cacheprovider`
- 32 preserved tests plus 15 new test cases (47 expected). Verify with pytest collection, not this estimate alone.
- UI: create or choose a venue in an active area, select category, create draft, submit, log in as a different verifier, review, verify, confirm history and audit. Verify collector cannot access another collector's drafts. Test unknown/free/paid pricing and explicit overnight start/end. Do not use a recovery account as a routine operator. Use synthetic data only in development.

Source candidate; local Python syntax, TypeScript transpilation and clean patch check do not constitute full runtime qualification. Do not merge before review. Preserve database volumes; never use `docker compose down -v` for an upgrade.
