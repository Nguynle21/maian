# ADR-0008: No application-level field encryption

**Status:** Accepted — 2026-08-16
**Type:** Accepted risk

## Context

The database holds immigration status and household income — the two most sensitive fields
in the system. Application-level encryption of those columns sounds obviously correct.

Managed PostgreSQL already encrypts at rest; TLS covers data in transit.

## Decision

**No application-level field encryption in v1.** Rely on platform encryption at rest, TLS in
transit, strict access control, mandatory 2FA, and soft deletes.

## Why not

Encrypting a column at the application layer:

- Breaks search, filtering, and sorting on that column — including the duplicate detection
  and worklist queries the system depends on
- Introduces **key management**, which is a genuinely hard moving part; done badly it makes
  the data permanently unrecoverable
- Protects mainly against an attacker who has already obtained database access, which — at
  three users on managed infrastructure — is not the dominant threat

The dominant threats are credential compromise and misconfiguration (see
`docs/security-baseline.md`), neither of which field encryption prevents: a logged-in
attacker sees decrypted data either way.

## Consequences

- An attacker with a database dump reads sensitive fields in plaintext. Accepted.
- If the threat model changes — a larger staff, a broader data set, or a regulatory
  requirement — this decision should be revisited with a superseding ADR.
- Recorded explicitly so a future maintainer knows this was a deliberate decision with
  reasoning, not an oversight. That is the honest way to skip a control.
