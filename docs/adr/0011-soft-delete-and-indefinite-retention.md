# ADR-0011: Soft delete only, indefinite retention

**Status:** Accepted — 2026-08-16

## Context

Customers churn, applications accumulate, and staff will want to remove clutter. Separately,
CMS requires agents and brokers assisting with Marketplace applications to retain consent
documentation for roughly ten years — so some records must survive a decade regardless of
what staff want.

The role model gives Admin the power to delete. That power is only safe if deleting is
reversible.

## Decision

**Nothing is ever hard-deleted in v1.** Records carry an `archived_at` timestamp. Archiving
hides a record from lists; the data remains. Only Admin can archive. Restore is available.

Retention is indefinite. There is no purge job and no expiry policy.

The word "deleted" is avoided in the interface and in the codebase. The term is
**Archived** (see `CONTEXT.md`).

## Alternatives rejected

- **Hard delete for Admin.** Matches user expectations from Excel, and makes the single
  worst human error — deleting hundreds of customers mid-enrollment — unrecoverable between
  nightly backups.
- **A retention/purge policy now.** Premature. Designing a deletion policy correctly
  requires knowing the regulatory picture in detail; it can be added in year three with full
  information and no data lost in the meantime.

## Consequences

- Every list query must filter out archived records. Enforce this once, at the model
  manager level, rather than remembering it at every call site.
- Storage growth is irrelevant: ~2,500 customers plus ~3,000 applications a year is a
  trivially small database for the foreseeable life of the agency.
- Human error is always recoverable, which is what makes "only Admin can delete" a safe
  power rather than a terrifying one.
- Deleting is irreversible; keeping is not. When uncertain, keep.
