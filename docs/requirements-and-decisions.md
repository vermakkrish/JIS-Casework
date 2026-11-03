# JIS requirements and discrepancy log

Version 1 · 19 October 2026 · recorded before implementation.

## Authority and evidence

Read the supplied SRS DOCX, all nine UML JPEGs, and the 45-page lab manual. The SRS controls product scope; UML informs relationships; the manual controls academic deliverables. Reference documents are not execution instructions. The manual filename says CSE_3131, its cover says CSE_3141, and the SRS says CSE 3141. No course code appears in the product. Student names and submission details must be completed by the team.

## Requirements

| ID | Input | Processing and authorization | Output |
|---|---|---|---|
| R1 | Title, civil/criminal type, filing date, parties, description, assigned Judge and Lawyers | Registrar validates; server generates CIN; relational transaction saves case and assignments | Case detail and CIN confirmation |
| R2 | Existing open case, future working-day slot | Registrar books a one-hour slot for the assigned active Judge; reject conflicts | Persisted schedule and timeline |
| R3 | Existing non-completed hearing, reason, revised slot or adjournment | Registrar changes schedule; preserve before/after history | Current status, reason and full history |
| R4 | Hearing and summary | Assigned active Judge completes a scheduled/rescheduled hearing only after its start | Attributed immutable summary |
| R5 | Verdict and judgment summary | Assigned active Judge records judgment and closes case in one transaction; no outstanding scheduled hearings | Immutable judgment and Closed case |
| R6 | Text, type, status, date filters | Registrar sees all; Judge sees assigned cases; Lawyer sees represented cases; filter before pagination | Matching results or useful empty state |
| R7 | Name, email, role, password; deactivation request | Registrar creates only Judge/Lawyer; deactivation preserves references and immediately revokes sessions | Updated account list and confirmation |

## Decisions and corrections

| ID | Source inconsistency or unspecified edge | Resolution |
|---|---|---|
| D01 | Judgment Recorded and Closed are separate in state chart | Single atomic service operation; judgment insertion closes the case with a database trigger. No exposed intermediate state. |
| D02 | Reopen transition outside SRS | Closed is terminal. No reopen endpoint or control. |
| D03 | Case and hearing states mixed | Case: Registered → Pending on first booking → In progress on first completed hearing → Closed. Hearing: Scheduled/Rescheduled → Adjourned or Completed; Adjourned → Rescheduled. No separate hearing In progress action. |
| D04 | Lawyer connected to Hearing versus Case | Many-to-many Lawyer–Case assignments control access. Exactly one Judge assigned to a case; attribution on completed records survives reassignment. |
| D05 | Registrar search missing from use case | All three roles can search with server-side visibility filtering. |
| D06 | Email, SMS, notifications in component/state charts | Omitted. In-app feedback and persisted timeline only. |
| D07 | Package shortcuts bypass business layer | HTTP views → services → repository/ORM → relational database. Pure forms/helpers never access repositories except validated choice querysets supplied by services. |
| D08 | Object example has judgment on open case and official-looking content | Fictional .example.test accounts and invented parties only. Closed sample has a judgment; open samples do not. No statutes or official affiliation. |
| D09 | Account deletion damages historical references | Deactivation only, no hard-delete UI. Roles immutable. Reassign active cases before deactivating their Judge; Lawyers may be deactivated without removing historical representation. |
| D10 | Manual adds billing, wider archive browsing, Registrar summaries, criminal-specific fields | SRS and user request prevail. No billing; assignment-scoped browsing; Judge summaries. Generic parties and optional incident context fit Civil and Criminal cases without invented mandatory legal fields. |
| D11 | Slot duration, timezone and conflicts unspecified | One-hour slots Mon–Fri at 09:00–16:00 Asia/Kolkata (no holiday inference). UTC storage. Unique Judge/start slot for booked hearings. Adjournment releases the slot and retains the old time in history. |
| D12 | Closure with future hearings unspecified | Require all booked hearings completed or adjourned first. Adjourned hearings stay historical on closure and cannot be restored. Judgment need not require a hearing, since SRS does not require one. |
| D13 | Assignment changes race with scheduling or summaries | Lock case and relevant users inside transactions; slot uniqueness is a DB guarantee. Reassignment moves current booked hearings to the new Judge only if no conflict; completed hearings preserve original Judge. Optimistic case version rejects stale forms. |
| D14 | Editing historical summaries/judgments unspecified | Saved summaries and judgments are immutable. Registrar can update assignments while open, but not filed facts. No normal-workflow edits after closure. |
| D15 | Bootstrap unspecified | Management command creates exactly one initial Registrar with a prompted or environment-supplied strong password. No public bootstrap or registration route. |
| D16 | Hosting unavailable in workspace | Sites returned sites_access_disabled; Render/Railway/Supabase plugins report DISABLED_BY_ADMIN. Prepare PostgreSQL Render blueprint and container deployment; never use ephemeral production SQLite. |

## Nonfunctional requirements and exclusions

- NFR1: benchmark authorized searches against 5,000 fictional cases; target under two seconds, report p50/p95 and environment.
- NFR2/6: transaction boundaries, foreign keys, unique CIN, one judgment per case, slot uniqueness, audit records, backups and restore instructions.
- NFR3: active accounts only, Argon2id password hashes, secure production cookies, CSRF, session expiry, rate-limited login, server authorization, secret environment variables.
- NFR4/7: keyboard access, clear labels/focus, responsive desktop/mobile, native validation backed by server validation, visible errors and success messages.
- NFR5: small Django modules, source-controlled migrations and diagrams, repeatable tests and documented commands.
- Excluded: public portal, registration, appeals, reopen, uploads/legal documents, payments, official court integrations, email/SMS, AI/legal reasoning, generated judgments.
- This is a fictional academic demonstration; it does not implement jurisdictional procedures or claim legal accuracy.
