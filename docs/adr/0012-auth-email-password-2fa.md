# ADR-0012: Email + password with mandatory 2FA

**Status:** Accepted — 2026-08-16

## Context

Three staff need to log in. The data includes immigration status and household income. The
most likely breach in the entire threat model is a compromised staff credential.

Two roles are required: **Admin** (one — the maintainer) and **Staff** (two). Both can view
and edit all 2,500 customers; only Admin can archive records, manage users, and export data.

## Decision

**Email + password with mandatory 2FA.** Accounts are created by the Admin — **no
self-signup**. Login rate limiting via `django-axes`, lockout after roughly five failed
attempts. Session expiry: **12 hours absolute, no idle timeout.**

Roles map onto Django's built-in groups and permissions rather than a hand-rolled system.

## Alternatives rejected

- **Google sign-in.** Fewer passwords to leak and staff likely already have Google accounts.
  Rejected because it makes "an attacker who phishes one Gmail account gets everything" the
  dominant failure mode, and the agency is not on Google Workspace with enforced 2FA. Worth
  revisiting if they move to Workspace.
- **Short idle timeouts (2 hours).** Rejected. Ten weeks of frantic data entry interrupted
  by re-authentication trains users to hate the software. The stolen-laptop case is better
  covered by mandatory full-disk encryption on the three laptops — a thief with a locked,
  encrypted laptop gets nothing regardless of session policy.
- **A hand-rolled permission system.** Django's is free, tested, and already understood by
  every AI assistant and future maintainer.

## Consequences

- Staff must use a password manager. This is mandated in writing alongside the other
  endpoint requirements (`docs/security-baseline.md`).
- Admin resets 2FA when someone loses their phone. Document this in the staff how-to.
- Offboarding is one click: **deactivate, never delete** — the change history must survive
  the person.
- A future customer-facing surface (e-signature) will need a separate authentication path;
  do not extend staff auth to customers.
