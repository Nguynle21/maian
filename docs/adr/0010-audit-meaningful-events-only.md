# ADR-0010: Audit meaningful events only; no read logging

**Status:** Accepted — 2026-08-16
**Type:** Partly an accepted risk

## Context

Three staff share all 2,500 customer records, and every one of them can edit. Some record of
who did what is necessary — for accountability between colleagues, and because the data is
sensitive.

Two axes were considered: **depth** (every field change vs. meaningful events) and
**breadth** (changes only vs. changes and reads). Logging every read of a customer record
was recommended, on the grounds that access logs are cheap to add and impossible to
reconstruct after an incident. It was declined.

## Decision

Log **meaningful events only, writes only**:

- Application stage transitions and payment status changes (the `ApplicationEvent` table,
  ADR-0004)
- Archive and restore
- Data exports — who, when, how many rows
- User management: account creation, deactivation, permission changes

**Not logged:** individual field edits on a customer record, and **who viewed a record.**

## Alternatives rejected

- **Full field-level history on every model.** Thorough, and a lot of storage and noise for
  three people who mostly trust each other. The events that need attribution are the ones
  that change a customer's *state* or move data *out* of the system.
- **Read logging.** Recommended and declined by the agency. Would have answered "who looked
  at this customer's immigration status, and when?"

## Consequences accepted

- After an insider incident it will be possible to see what a user *changed* and *exported*,
  but not what they *read*. Export logging partially covers the worst case — bulk
  exfiltration — since a full export is admin-only and logged.
- Recorded as a decision, not an oversight. Revisit if staff count grows or if a regulatory
  obligation requires access logs.
