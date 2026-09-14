# Context: Maian

An internal CRM for a health-insurance agency in Missouri City, Texas. Three staff serve
roughly 2,500 customers, most of whom enroll in ACA Marketplace health coverage during the
annual Open Enrollment window.

The system exists to do three things: capture customer information reliably, tell three
overworked people what to do next during Open Enrollment, and send occasional bulk SMS.
Nothing else.

## Who uses it

Three staff, non-technical, on laptops, always online, in one office. No customer ever logs
in. There is no public surface beyond the login page.

## The shape of the year

Open Enrollment runs **November 1 – January 15**. Essentially every customer files a new
application in that window, and follow-up work (missing documents, missing payments) tails
off through **March**. The rest of the year is servicing and quiet.

This seasonality is the single most important fact about the system. The software's job
between November and March is to tell three exhausted people what to do next. Design for
fast repeat data entry and clear worklists, not for browsing or analytics.

## Glossary

Use these terms exactly. Do not drift to synonyms.

**Customer** — a person the agency serves. Not "client", not "lead", not "contact".
Holds identity, contact, residency, immigration, and household-income information. No SSN
is ever stored.

**Household Member** — a spouse or dependent attached to a Customer. One entity with a
`relationship` field (`spouse` | `dependent`), not separate spouse and dependent types.
Dependents carry a **Public Coverage** value (`none` | `chip` | `medicaid` | `medicare`) —
dependents include children and elderly parents. Every Household Member carries an
immigration status. A Household Member may later be linked to their own
Customer record; they are never duplicated.

**Product** — a line of coverage: Health, Dental, Travel. Stored as a database row, not a
code enum, so an admin can add one without a deploy.

**Plan Year** — the coverage year an Application belongs to. Applications are never
overwritten year to year.

**Application** — the unit of enrollment work, scoped to `(Customer, Product, Plan Year)`.
A customer holds at most one active Health application at a time, and may hold Dental and
Travel alongside it. This is the entity that carries status.

**Stage** — where an Application sits in the enrollment pipeline. Mutually exclusive:
`submitted_pending` → `approved_missing_docs` → `completed`, plus `withdrawn` as a terminal
exit. A denial is not a stage — the agency always retries, so a denied application remains
pending from the staff's point of view.

**Payment Status** — `current` | `missing`. Independent of Stage; an Application can be
missing payment at any stage. Never fold this into Stage.

**Docs Due On** — the deadline the carrier gives the customer to complete documents and
payments. Entered manually by staff at enrollment. Drives every reminder in the system.

**Application Event** — an append-only record of a Stage or Payment Status transition:
who, when, from, to, optional note. The history of an Application, never edited or deleted.

**Policy** — active coverage resulting from a `completed` Application. **Not a separate
entity.** Carrier, plan name, premium, and policy number live only inside PDFs in the Vault
(see ADR-0007). Once an Application reaches `completed`, status tracking stops.

**Vault** — per-Customer document storage. PDFs and images in private S3-compatible object
storage, reached only through short-lived presigned URLs.

**Worklist** — the home screen. Filtered buckets of Applications needing action
(`Overdue`, `Due ≤ 7 days`, `Due ≤ 30 days`, `Missing payment`, `Missing documents`,
`Opted out — needs a call`). Not a dashboard. No charts.

**Send** — one bulk SMS operation: staff compose free text, filter an audience, review the
queue and the cost, then send once. Not "campaign".

**SMS Opt-Out** — a per-Customer flag, set automatically when Twilio reports a STOP.
Opted-out customers are excluded from every Send in code, not by staff discipline.

**Archived** — the soft-delete state. Records are hidden from lists but never removed.
Avoid the word "deleted" — nothing is hard-deleted.

**Admin / Staff** — the two roles. Both can view and edit all 2,500 customers. Only Admin
can archive records, manage users, and export data.

## Out of scope

Deliberately, and not up for reopening without a new ADR:

- Customer-facing anything — no portal, no self-service, no customer login
- E-signature (planned for a later year; would introduce the first customer-facing surface)
- Commission tracking and accounting
- Carrier-portal integration
- AI features
- Rolling last year's application forward — impossible in year one; belongs to the OE 2027 build
- Native or mobile apps, offline mode
- Storing SSNs or card numbers, ever

## Related documentation

- `docs/scope-and-timeline.md` — what ships when, and the launch plan
- `docs/security-baseline.md` — required configuration and the incident plan
- `docs/adr/` — every architectural decision, with its rejected alternatives
