# Architecture and implementation notes

JIS is a small server-rendered Django application. Keeping templates and form posts on the same origin removes the need for a separate client token store, CORS policy, SPA state synchronization, or a second deployable service. Python/Django was selected because the environment supports Python 3.12 and Django provides mature authentication, CSRF, forms, migrations, and an ORM. PostgreSQL provides durable relational storage and real row locks. SQLite is supported only for low-concurrency local development; production configuration refuses it.

## Layers

`templates/` and `static/` present information. `core/views.py` routes HTTP requests, invokes forms, and formats responses. `core/services.py` enforces role, visibility, transitions, active assignments, field limits, and concurrency rules. `core/repository.py` centralizes persistence helpers and transactions; `core/models.py` and migrations define database structure. Django relation reads in case details and dashboard aggregates are intentionally compact ORM usage; all consequential writes go through the service boundary. The corrected package diagram makes that adaptation explicit.

## Data dictionary

| Entity | Purpose and integrity |
|---|---|
| User | Unique normalized sign-in/email, name, Argon2id hash, role restricted to Registrar/Judge/Lawyer, active flag. No role-changing UI. |
| Case | UUID identity, unique CIN, type constrained to Civil/Criminal, facts/parties, filing date, Judge and Registrar FKs, status, version, timestamps. Closed timestamp must agree with Closed state. |
| Representation | Unique Case/Lawyer pair, assigned-by user and timestamp. Current assignments determine visibility; removals remain described in the audit timeline. |
| Hearing | FK to Case and Judge, UTC start, state, attributed summary and completion time. Unique Judge/start among booked rows; one booked hearing per Case. Adjourned rows require a null current time. Completed rows require a summary, author and timestamp. |
| HearingChange | Hearing/actor FKs, old/new state and UTC time, reason, timestamp. Initial booking, rescheduling, adjournment and completion each add a record. |
| Judgment | One-to-one Case FK, author FK, verdict, summary, timestamp. Insert trigger validates the case and closes it. Update trigger prevents alteration. |
| AuditEvent | Attributed consequential action, optional Case FK, plain-text detail, timestamp. No edit/delete web endpoints. |
| Django Session | Database-backed session with signed data, expiry and authenticated user identity. Active status rechecked by authentication backend on requests. |
| LoginThrottle | SHA-256 email/IP keys, attempt counts and 15-minute expiry. No plaintext password or IP in this table. |

Foreign keys use PROTECT for historical user and case references. Indexes cover CIN, Judge/status, filing date, hearing time, action time, and foreign-key columns. Search is case-insensitive over CIN/title/parties with scoped SQL before pagination. Small project volumes do not need a separate search engine.

## Transactions and concurrency

Each mutation locks the Case and relevant User rows (sorted user IDs), rechecks active access, and validates the submitted Case version. Scheduling has a database uniqueness backstop, so a racing second request rolls back and receives a plain conflict message. Reassignment moves only booked hearings; completed records preserve original Judge attribution. Registrar creation locks actors/assignees and stores assignments and audit with the Case in one transaction.

CIN format is `JIS-YYYY-XXXXXXXXXXXX`: a 48-bit cryptographically random server suffix, unique database index, and up to five transaction retries on insert collision. It is intentionally not sequential; the UUID primary key is separate. No browser counter exists. For this project volume, collision retries are rare; uniqueness is enforced by the database regardless of probability.

Judgment insertion invokes a database trigger: the Case must be open, the author must match its assigned Judge, and no booked hearing may remain. The INSERT closes the Case and increments its version in the same database transaction. The service adds the audit event before commit. A tested injected audit failure rolls back the judgment and closure together. Closed Case updates, new/changed hearings on closed Cases, completed-hearing edits and judgment updates are rejected by database triggers. Application guards provide human-readable errors first.

## Security boundary

Production requires a long random environment secret, PostgreSQL, HTTPS, exact allowed hosts, Secure/HttpOnly/SameSite session cookies, secure CSRF cookies, and trusted proxy scheme handling. Django escapes content and parameterizes ORM SQL. CSP permits only same-origin scripts/styles, forbids frames and object content, and restricts form destinations. No user uploads are accepted. Authentication, action and assignment checks are on the server. Invisible controls are only a usability feature. CSRF protection covers sign-in and every state-changing form; logout is POST-only.

The first Registrar is created by a management command, never a public HTTP endpoint. PostgreSQL advisory locking prevents duplicate first-bootstrap creation. All other accounts are created by a Registrar. Access removal is deactivation. The application does not provide a public password-reset workflow or send messages; the project operator can use Django’s prompted `changepassword` command.

## Operational limits

The application is an academic prototype with meaningful controls, not an audited court-production platform. No MFA, jurisdiction-specific procedure, holiday calendar, cross-court integrations, archival retention policy, high availability, legal decision support or notifications are claimed. Privileged database operators can alter records; the audit is application-append-only, not cryptographically tamper-evident. Backups, dependency patching, secret rotation, capacity monitoring and real-host smoke testing remain operator responsibilities. Use only fictional data.
