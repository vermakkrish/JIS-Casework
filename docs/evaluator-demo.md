# Seven-minute evaluator demonstration

Before presenting, use a separate fictional demo database and run `seed_demo`. Keep three browser profiles or private contexts signed in separately. Know the seed password without projecting it. Open this guide, the requirements matrix, and the rendered model index. Do not reset data while the evaluator is using the app.

| Time | Presenter | Demonstration and explanation |
|---|---|---|
| 0:00–0:45 | Student 1 | Introduce the scope: internal case records and hearing schedules, exactly three roles, fictional data, no official affiliation. Show the corrected case/hearing state model. Explain why the SRS overrides billing and Registrar-summary details in the manual’s example. |
| 0:45–2:00 | Student 1 | As Registrar, create a Lawyer account, then register “Fictional Birch Studio v. Lantern Works.” Select Mira Dev and Rohan Vale. Show the generated CIN and persisted confirmation. Explain server-generated randomness plus database uniqueness; there is no browser counter. |
| 2:00–3:00 | Student 1 | Schedule a future weekday slot. Reschedule with a reason, then adjourn. Expand schedule history to show both times, reason, actor, and status. Explain one-hour slots and conflict prevention. Show the assignment controls and access impact. |
| 3:00–4:20 | Student 2 | As Mira Dev, open the seeded Orchid House case whose historical hearing is ready. Save a fictional hearing summary. Show Completed hearing and In progress case. Record a verdict and judgment summary, confirm closure, and refresh. Show Closed status and final judgment. Explain the transaction and database trigger; no reopen feature exists. |
| 4:20–5:15 | Student 3 | As Rohan Vale, search for the new CIN, filter open cases, inspect case history, and use the hearing agenda. Explain read-only access. In the second Lawyer context, open the same case URL: show the 404 access boundary. |
| 5:15–5:50 | Student 1 | Deactivate the newly created Lawyer. Show that the account remains marked Inactive and historical attribution is preserved. Explain why deleting referenced people would damage records. |
| 5:50–7:00 | Student 2 + Student 3 | Present the traceability matrix, PostgreSQL test results, concurrent slot/CIN tests, rollback test, measured search results, mobile screenshot, and deployment status honestly. Point to the README’s reproducible commands and the current live-deployment evidence. |

Suggested work division for learning and viva preparation: Student 1 explains forms, Registrar workflow, accessibility and presentation; Student 2 explains models, database constraints, transactions, concurrency and Judge workflow; Student 3 explains authorization, testing, diagrams, operations and deployment. All three should run the full demo and be able to explain the scope decisions.

Possible questions: Why PostgreSQL? Why deactivation? What happens if audit recording fails during judgment? How do two simultaneous slot bookings resolve? Can a Lawyer inspect an arbitrary UUID? Why is a pending case different from an adjourned hearing? What does the measured search performance include? How do you restore a backup without breaking judgment triggers?
