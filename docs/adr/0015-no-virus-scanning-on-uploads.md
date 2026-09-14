# ADR-0015: No virus scanning on uploaded files

**Status:** Accepted — 2026-08-16
**Type:** Accepted risk

## Context

The Vault is the largest new attack surface in the system: staff upload PDFs and images
received from customers. The generic advice is to scan every upload for malware.

## Decision

**No virus scanning in v1.** The following mitigations are implemented instead, and are
mandatory:

- Extension whitelist: `.pdf .jpg .jpeg .png` only
- 10 MB size cap
- Randomized stored filenames; the uploaded filename is never trusted for a path
- Private bucket; files served only via short-lived presigned URLs after a permission check
- `Content-Disposition: attachment` so nothing ever renders in the application's origin

## Why not

The uploaders are the agency's own three staff, uploading documents they received directly
from customers they know. Files are never executed on the server, never rendered in the
browser's origin, and never served to the public. ClamAV or a scanning API is a genuine
moving part — a daemon or a paid dependency, plus a failure mode when it is down — for a
threat that barely applies to this workflow.

The most realistic residual risk is a staff member downloading a malicious PDF that a
customer sent them. That risk exists today via email and Dropbox and is properly addressed
at the endpoint, not in this application.

## Consequences

- A malicious file could sit in the Vault and be downloaded by a staff member. Accepted;
  mitigated by endpoint protections (`docs/security-baseline.md`).
- Revisit if the Vault ever accepts uploads from customers directly — a customer-facing
  upload surface changes this calculation entirely and requires a superseding ADR.
- Recorded explicitly so a future maintainer knows this control was considered and
  deliberately skipped, with reasons.
