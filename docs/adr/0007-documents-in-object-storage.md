# ADR-0007: Documents in object storage; policy details stay unstructured

**Status:** Accepted — 2026-08-16

## Context

Staff need a per-customer vault of PDFs and images. Separately, the agency decided that
policy details — carrier, plan name, policy number, monthly premium, effective date — should
live *only inside those PDFs*, to be opened and read, rather than as structured fields.
Adding five columns now was proposed and declined.

The vault was originally scheduled for December, after launch. That was reversed: the
"Approved but Missing Documents" stage means documents are actively collected *during* Open
Enrollment, so deferring the vault would split one workflow across two systems during the
busiest ten weeks of the year — the fastest way to make staff distrust the new tool.

## Decision

**Files go to private S3-compatible object storage (Cloudflare R2), not into the database.**
Database rows hold metadata and a storage key.

A **minimal vault ships in v1**: upload a file to a customer, list files, download,
admin-only archive. No tagging, no preview, no folders, no retention automation. The daily
email digest was cut instead to protect the schedule.

**No structured policy fields.** Carrier, plan, premium, and policy number exist only inside
documents.

## Alternatives rejected

- **Files as database blobs.** Simpler to back up, but bloats the database, slows every
  dump, and makes serving files expensive. Object storage is the boring correct answer.
- **Public bucket with obscure URLs.** Rejected. The bucket is private; files are reached
  only through short-lived presigned URLs issued after a permission check, with
  `Content-Disposition: attachment` so nothing renders in the browser's origin.
- **Structured policy fields.** Recommended and declined. Five columns are free to add to an
  empty table and expensive to add to 2,500 live rows.

## Consequences accepted

- Commission tracking in a later year will require re-keying policy details by hand from
  PDFs, customer by customer.
- Questions like "how many customers are with this carrier?" cannot be answered without
  opening documents one at a time.
- These are reasonable trades for v1 and revisitable: structured fields can be added in year
  two, when commissions actually matter, with a new ADR superseding this one.
- Upload constraints and security handling are covered in `docs/security-baseline.md` and
  ADR-0015.
