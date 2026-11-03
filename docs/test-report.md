# Verification report

Verification date: 19 October 2026, Asia/Kolkata. The evidence covers the **local application and PostgreSQL database**, not a public live deployment. There is no verified external URL yet.

## Environment and result summary

- Windows 11 (10.0.26200), Python 3.12.14, Django 5.2.18, PostgreSQL 18.4 bound to loopback. The PostgreSQL binaries came from the `embedded-postgres` npm distribution; the app is not dependent on that package in production.
- **27/27 backend tests pass on PostgreSQL**, including the two threaded concurrency tests. Final suite duration: 3.794 seconds. SQLite local compatibility: 25 pass, two PostgreSQL-only concurrency tests explicitly skipped.
- **9/9 browser acceptance groups pass** on Microsoft Edge/Chromium. Desktop viewport 1440×1000; mobile viewport 390×844. No browser JavaScript errors were observed.
- Five automated axe WCAG A/AA scans (login, overview, case detail, mobile case detail, agenda) report **zero violations**. This is bounded automated evidence, not a claim of complete accessibility certification. Native links, forms and controls provide keyboard interaction and visible focus.
- Production `check --deploy --fail-level WARNING`, migration-drift check, static collection and Python compilation pass. Docker execution and live-host checks remain pending.
- All 12 corrected DOT models parse and render successfully to SVG. The HTML diagram viewer links to each editable source.
- PostgreSQL process interruption/restart recovered the persistent cluster; a complete record digest across seven application tables matched before and after. No Closed/judgment mismatch exists. See the JSON evidence for counts and digest.

## Test-case table

| ID | Scenario | Expected result | Actual result | Status |
|---|---|---|---|---|
| T01 | Register valid case and duplicate CIN attempt | Saved case, representation and audit; DB rejects duplicate CIN | All assertions met | PASS |
| T02 | Invalid case title / Lawyer registration attempt | Validation/permission rejection; no extra Case | No extra Case saved | PASS |
| T03 | Schedule hearing and competing same-Judge case | Correct FK and Pending state; conflict rejected | One booking persisted | PASS |
| T04 | Half-hour slot / summary before hearing starts | Invalid slot and premature summary rejected | Both rejected | PASS |
| T05 | Reschedule, adjourn, reschedule again | Reason required; before/after values retained; adjourn clears slot | Four history records; final Rescheduled state | PASS |
| T06 | Assigned Judge summary and replacement attempt | Complete hearing, attribute author, case In progress; reject replacement | Expected states/author; replacement rejected | PASS |
| T07 | Hearing from another Case passed to summary | No cross-case update | Relation lookup rejects it; summary unchanged | PASS |
| T08 | Judgment and closure; try new hearing, reassignment or second judgment | One judgment; Closed case; all later mutations rejected | Expected terminal state and rejections | PASS |
| T09 | Inject audit-write failure during judgment | Roll back judgment and closure together | Zero judgments; original Registered state retained | PASS |
| T10 | Judgment with outstanding booked hearing | Reject without judgment | No judgment inserted | PASS |
| T11 | Scoped search and arbitrary Case UUID | Registrar sees all; Judge/Lawyer only assigned; unassigned detail 404 | Query counts and 404 match | PASS |
| T12 | Create Lawyer, sign in, then deactivate | Argon2id hash; active session loses access; account preserved | All expected behavior observed | PASS |
| T13 | Deactivate assigned Judge, reassign and retry | Block while open cases assigned; permit after reassignment; preserve history | Open-case guard and history assertions pass | PASS |
| T14 | Registrar creation/deactivation via R7 | Reject unsupported account role and protected Registrar | PermissionDenied | PASS |
| T15 | Stale assignment form version | Reject lost update | ValidationError and unchanged assignments | PASS |
| T16 | Move case to Judge with conflicting booking | Roll back Judge, Lawyers and hearing transfer | Original relationships retained | PASS |
| T17 | Direct ORM attempts to close without judgment, edit closed case or judgment | DB rejects invalid writes independently of UI/service | Integrity errors; no inconsistent record | PASS |
| T18 | Duplicate representation / delete referenced Judge | Unique pair and protected reference | Both rejected | PASS |
| T19 | Unauthorized POSTs for Registrar/Judge operations | Backend 403 regardless of hidden controls | All tested routes return 403 | PASS |
| T20 | Missing CSRF token; GET logout | POST 403; GET 405 | Exact expected responses | PASS |
| T21 | Exceed login-attempt window | Attempts limited; UI response 429 | Rate-limit guard and HTTP status pass | PASS |
| T22 | Invalid registration POST and script text in description | 422, no saved invalid Case; escaped HTML | Validation and escaping assertions pass | PASS |
| T23 | Malformed search date/page | Useful validation, no crash | HTTP 200 with field error | PASS |
| T24 | Inactive Judge assigned to new case | Reject inactive target | ValidationError | PASS |
| T25 | Lawyer queries availability; weekend slots | Registrar-only endpoint; no weekend availability | 403; zero available slots | PASS |
| T26 | 24 registrations across six threads | All CINs unique and all Cases saved | 24 distinct CINs / 24 Cases | PASS |
| T27 | Two threads book same Judge and time | Exactly one winner, no duplicate slot | One success, one conflict, one Hearing | PASS |
| UI01 | Registrar signs in, opens overview | Data-backed dashboard | Visible expected heading and persisted counts | PASS |
| UI02 | Registrar registers via rendered form | Confirmation, unique CIN, detail | Saved CIN parsed from detail | PASS |
| UI03 | UI schedule, reschedule, adjourn, history and assignment update | Current status plus visible reasons/history | All confirmations and history visible | PASS |
| UI04 | UI account creation and deactivation | New account then preserved inactive row | Both operations confirmed | PASS |
| UI05 | Lawyer UI search/detail/agenda and unauthorized POST | Read-only authorized view, rejected write | Read views available; POST 403 | PASS |
| UI06 | Judge saves historical hearing summary | Correct hearing completed | Attributed summary and completion message | PASS |
| UI07 | Judge records judgment, then reloads | Closed record and judgment persist | Verdict survives reload; closure control absent | PASS |
| UI08 | Other Lawyer opens known Case URL | 404 | 404 | PASS |
| UI09 | Responsive, axe and script-error checks | No horizontal page overflow at 390 px; no tested violations/errors | All five axe scans clean; zero script errors | PASS |
| P01 | Restart PostgreSQL using same data directory | All application records unchanged | Seven-table SHA-256 identical; zero closure mismatches | PASS |
| P02 | Sign in as all three roles after application/database restart | Persisted Orchid judgment and Closed state; account management denied to Judge/Lawyer | All three browser checks pass | PASS |
| B01 | Production Django checks / compilation / static build | No issues, no migration drift, successful artifacts | All commands exit 0 | PASS |
| D01 | Parse/render 12 corrected text models | Valid SVG for each | 12 SVG files generated | PASS |
| L01 | External HTTPS deployment and all-role live smoke | Real live URL with persistent DB | Workspace hosting disabled; no credentials | BLOCKED |
| O01 | Restore backup on real host | Data and all-role smoke verified | Backup/restore runbook prepared; runtime lacks dump/restore tools | NOT RUN |
| O02 | Build/run container on Docker | Image and Compose smoke verified | No Docker daemon available | NOT RUN |

Backend ID order maps to the named test methods in `core/tests/test_workflows.py` and the traceability matrix. Browser groups are machine-recorded in `browser-results.json`.

## Search performance

5,006 total cases (5,000 temporary synthetic records plus six seed cases). The benchmark runs the Django HTTP test client through authentication, permission-filtered ORM queries, pagination and complete HTML rendering. Each role runs five warm-ups and fifty measured serial requests across four query patterns: broad title match, narrower title match, exact-like CIN substring and no-match search. PostgreSQL is on loopback, data is warm, and no concurrent production traffic is simulated. Browser paint, DNS, internet, reverse proxy and TLS overhead are excluded. Synthetic fixtures and benchmark sessions are rolled back.

| Role | Requests | Median | p95 | Maximum | Under 2 s in this test |
|---|---:|---:|---:|---:|---|
| Registrar | 50 | 15.44 ms | 27.02 ms | 33.07 ms | Yes |
| Judge | 50 | 16.17 ms | 27.41 ms | 29.85 ms | Yes |
| Lawyer | 50 | 14.37 ms | 38.93 ms | 41.11 ms | Yes |

This meets the SRS target under the stated project-sized local conditions. It is not a universal latency guarantee. Repeat the benchmark and browser measurements on the chosen host before claiming live performance.

## Evidence inventory

- `evidence/browser-results.json`: actual browser test IDs, target, viewports and result.
- `evidence/accessibility-*.json`: five actual axe violation lists (empty after corrections).
- `evidence/search-performance.json`: measured environment and latency distributions.
- `evidence/release-checks.json`: production checks and build command outputs.
- `evidence/persistence-and-restore.json`: restart digest and explicit unrun restore limitation.
- `evidence/post-restart-smoke.json`: all three roles checked again after restart.
- `evidence/diagram-validation.json`: twelve source/render pairs verified; domain, sequence and state diagrams visually inspected.
- `evidence/backend-postgresql.txt`, `evidence/backend-sqlite.txt`: concise final suite outcomes.
- PNGs: login, Registrar overview at desktop/mobile, case detail at desktop/mobile, Lawyer agenda, final judgment.

Earlier verification found low contrast in secondary text and table headings; these were corrected and the final axe scans pass. Test harness issues with required-field labels and threaded connection cleanup were corrected; the final PostgreSQL suite cleanly destroys its test database. No failed earlier screenshot is presented as final evidence.
