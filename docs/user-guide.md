# JIS user guide

JIS Casework is an internal academic demonstration with fictional records. It is not an official court service and does not provide legal advice. All hearing times are displayed in **Asia/Kolkata (IST, UTC+05:30)**. Stored timestamps are UTC.

## Sign in and account safety

Use the account given to you by the Registrar. There is no public sign-up. Change your initial password through the sidebar and sign out on shared devices. Passwords must be at least 12 characters and pass Django’s common-password and similarity checks. Sessions expire after eight hours. Ten attempts for an email address or fifty for an IP in a 15-minute window temporarily block further sign-in attempts; successful attempts also count toward the window. No email or SMS is sent.

Forgotten passwords require the project operator to run `python manage.py changepassword <account-email>` from a trusted shell. Password entry is hidden. Do not put passwords into a source file, screenshot, terminal argument, report, or Git commit.

## Registrar

1. Open **People & access → Create account**. Enter a fictional name, email, Judge or Lawyer role, and strong password. Share the password privately; ask the holder to change it after sign-in.
2. Open **Case register → Register case**. Enter a title, type, filing date no later than today, initiating party, respondent, description, one active Judge, and at least one active Lawyer. The confirmation displays the saved CIN.
3. Open the case and select **Schedule hearing**. Choose a future weekday and an available one-hour slot. Slots start at 09:00–16:00 IST, Monday–Friday. A Judge cannot have two booked hearings in the same slot; a case cannot have two currently booked hearings. Public holidays are not modeled.
4. To change a booking, use **Reschedule** and enter a different slot and a reason of at least five characters. **Adjourn hearing** requires a reason and releases the slot without choosing a new date. Reschedule the adjourned hearing when ready. Expand **Schedule history** to compare old and new values and see the actor and timestamp.
5. **Update assignments** changes the Judge and/or Lawyers on an open case, with a reason. Booked hearings move to the new Judge only if there is no conflict. Completed hearing authors and judgment authors remain unchanged. Former Lawyers lose visibility when removed; the assignment change remains in the timeline.
6. Search by CIN, title, or party, and filter by state, type, and filing dates. The “All open cases” filter includes Registered, Pending and In progress.
7. To remove access, choose **Deactivate** on a Judge or Lawyer. First reassign every open case held by a Judge. Confirm and supply a reason. This prevents sign-in and invalidates existing access on the next request. The account row remains to preserve historical references. No hard-delete or reactivation UI exists.

The Registrar cannot enter hearing summaries or judgments. Filed facts are not normally editable; assignment changes are the supported amendment workflow.

## Judge

The overview and register contain only your currently assigned cases, including closed records still assigned to you. Cases not assigned to you are unavailable even if you know the URL.

After a booked hearing’s start time, open its case and choose **Record summary**. Enter the proceedings summary, review it, and check the confirmation box. Saving completes the hearing, attributes the summary to you, and advances the case to In progress. Saved summaries cannot be edited.

When ready for final disposition, ensure every booked hearing is completed or adjourned by the Registrar. Choose **Record judgment & close**, provide the verdict and judgment summary, and confirm. One transaction inserts the judgment, closes the case, and records the audit event. If the transaction fails, none of these changes remain. A closed case is final: no new hearings, assignments, judgment edits, or reopening.

## Lawyer

Your register contains only cases you represent. Search, filter, read the case overview, inspect hearing histories and summaries, and read judgments. Use the agenda to see hearings on a chosen date. Your role is read-only; ask the Registrar about assignments or schedule changes. Historical access does not expand to all archived cases.

## Understanding status and feedback

- **Registered:** case saved; no hearing booked yet.
- **Pending:** first hearing has been scheduled; an adjournment does not reset the case.
- **In progress:** at least one hearing summary has been completed.
- **Closed:** final judgment recorded and case closed together.
- Hearing states are separate: **Scheduled, Rescheduled, Adjourned, Completed**. Adjourned means there is no current slot. Old dates are visible in history.
- If a form says the record changed, reload the case before retrying. This protects against overwriting another user’s work. Failed validation preserves non-secret form entries.
- A success message appears only after a successful write. Check the case timeline or refresh the page to confirm the stored result.

## Fictional demonstration accounts

| Email | Role | Name |
|---|---|---|
| registrar@jis.example.test | Registrar | Avery Sen |
| judge@jis.example.test | Judge | Mira Dev |
| lawyer@jis.example.test | Lawyer | Rohan Vale |
| judge.two@jis.example.test | Judge | Ishan Reed |
| lawyer.two@jis.example.test | Lawyer | Leela Moss |

The generated local password is in `private/demo-access.json` on the project machine. This directory is excluded from Git, the source archive, and Docker. It is not a public demo credential. New installations provide their own `DEMO_PASSWORD`; every seeded account initially uses that value. Production accounts should receive separate passwords through account creation or operator password changes.

## Resetting the dedicated demo database

These commands delete **every record in the selected database** and create new fictional fixtures. Check `DATABASE_URL` first; never run this against records you need to retain.

```powershell
# Supply a new private value in this terminal session.
$env:DEMO_PASSWORD = Read-Host 'Demo password' -MaskInput
python manage.py seed_demo --reset --confirm-fictional-reset
Remove-Item Env:DEMO_PASSWORD
```

For a dedicated hosted demo, an operator must additionally set `ALLOW_DEMO_SEED=1`. Remove it after seeding. Do not leave seed/reset commands on automatic deployment. The seed creates six cases, including three future hearings, one historical hearing awaiting a summary, one closed case, and one case assigned exclusively to the second Judge/Lawyer. That historical hearing is explicitly labeled as a demonstration fixture; the normal scheduling UI forbids past slots.
