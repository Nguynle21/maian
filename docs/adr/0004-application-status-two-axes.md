# ADR-0004: Application status as two orthogonal axes plus an event log

**Status:** Accepted — 2026-08-16

## Context

Staff described status as three tiers — "Submitted and Pending", "Approved but Missing
Documents", "Completed" — each of which additionally needs "Missing Payment" and an
expiration date. Expressed that way it reads as one list with sub-tiers.

It is not. Payment can be missing at *any* stage, and the expiration date is not a status at
all — it is the deadline the carrier gives the customer to complete documents and payments,
entered manually by staff at enrollment.

Flattening these into one dropdown causes combinatorial explosion: six or nine options that
staff must scan, growing every time a new flag appears.

## Decision

Three separate fields on `Application`:

```
stage           submitted_pending → approved_missing_docs → completed
                (+ withdrawn, terminal)
payment_status  current | missing            ← independent of stage
docs_due_on     date                         ← manually entered; drives all reminders
```

Plus an **append-only `ApplicationEvent` table** recording every stage and payment
transition: who, when, from, to, optional note. Never edited, never deleted.

Reminder thresholds are **configuration, not hardcoded numbers**. Worklist buckets:
`Overdue`, `Due ≤ 7 days`, `Due ≤ 30 days`.

## Notes on the state machine

- There is **no `denied` stage.** The agency always retries a denial, so from the staff's
  point of view the application is still pending. Adding a state nobody acts on differently
  is noise.
- `withdrawn` is the only failure exit. A state model with no failure exit forces staff to
  lie to the system.
- Mid-year plan changes are *policy servicing*, not enrollment, and sit outside this machine.
- After `completed` the Application becomes an active policy and **status tracking stops.**
  This machine exists only for the November–March enrollment cycle.

## Alternatives rejected

- **A single `status` enum with combined values.** Simpler on day one, unmanageable by the
  third flag, and it makes "show me everyone missing payment" a query across many values.
- **Current status only, no event log.** One less table, but no history, no accountability
  between three staff sharing records, and nothing to show under a retention regime. The
  event log is one table and near-zero complexity — the cheapest high-value structure in the
  schema.

## Consequences

- Current stage may be denormalized onto `Application` as a cached column for query
  simplicity; the event log remains the source of truth for history.
- Adding a future flag (e.g. "needs interpreter") is a new column, not a rewrite of the enum.
- Thresholds can be tuned in January from real experience without a deploy.
