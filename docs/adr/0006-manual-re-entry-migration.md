# ADR-0006: Manual re-entry migration with a hard cutover

**Status:** Accepted — 2026-08-16

## Context

The ~2,500 customers currently live in Excel files shared over Dropbox. The data is very
messy and contains sensitive fields the new system deliberately does not carry (no SSN).

Two paths were weighed. An automated import into a "staging" state — all fields nullable,
records marked unverified until a human confirms them — converts a large upfront blocking
task into incremental cleanup. Manual re-entry treats the new system as a fresh start.

The upfront cost of manual re-entry was estimated and put to the agency: roughly 2,500
records × ~4 minutes ≈ **165 hours**, about 55 hours per staff member. The concern was
raised explicitly and the agency chose manual re-entry anyway, because the existing data is
messy enough that importing it would import the mess, and because it contains fields that
should not migrate.

## Decision

**No automated import.** Staff re-enter customers by hand through the intake form.

The re-entry is not a separate project: during Open Enrollment staff touch every customer
anyway, so entering them into the new system is a byproduct of work already being done.
This is why the launch date is pinned to the enrollment window.

**Hard cutover on November 1, 2026.** Dropbox becomes read-only reference. No dual entry.

## Alternatives rejected

- **Staged import with human verification.** Technically the safer migration and the one
  initially recommended. Rejected on the agency's judgement about data quality; recorded
  here so the reasoning is visible if the decision is ever revisited.
- **Dual-running both systems through Open Enrollment.** Rejected outright. Running two
  systems through a ten-week crunch is the most reliable way to get a new system abandoned.

## Consequences

- For the first weeks of Open Enrollment the two systems disagree, and any customer not yet
  touched exists only in Dropbox. Bounded by the fact that OE forces every customer to be
  touched within ten weeks.
- Data quality in the new system starts high, because a human read every field.
- The launch date is not negotiable without losing the migration window and slipping a year.
- Because staff re-enter in parallel, duplicate records are likely — hence the live
  duplicate warning at entry time (ADR-0004 companion behaviour, implemented in the form).
