# Security Baseline

## Threat model

The data at risk is names, dates of birth, addresses, phone numbers, **immigration status**,
and **household income** for ~2,500 people. No SSNs, no card numbers. Immigration status is
the field whose exposure causes the most real-world harm to a real person.

| Threat | Likelihood | Impact | Primary control |
|---|---|---|---|
| Staff credential phished or reused | High | Total | Mandatory 2FA, login rate limiting |
| Misconfiguration (`DEBUG=True`, secret in git, public bucket) | High | Total | Checklist below, security review milestone |
| Departing staff exports the database | Medium | Total | Admin-only export, export logging, same-day offboarding |
| Lost or stolen laptop | Medium | Total | Full-disk encryption on all laptops |
| Automated vulnerability scanning by bots | High | Low | Django defaults, Dependabot |
| Targeted attacker writing custom exploits | Very low | Total | Not defended against; accepted |

The real risks are human and configurational, not sophisticated. Effort goes there.

## Required configuration — verify before every deploy

- [ ] `DEBUG = False` in production. With it on, any error page prints environment
      variables — including database credentials — to whoever triggered it.
- [ ] `SECRET_KEY` and all credentials in platform environment variables. Never in git.
      `.gitignore` in place from the first commit.
- [ ] `ALLOWED_HOSTS` set to the real hostname.
- [ ] HTTPS enforced, HSTS enabled, `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE` on.
- [ ] Login rate limiting (`django-axes`), lockout after ~5 failed attempts.
- [ ] Django admin served from a non-default, non-guessable path.
- [ ] Object storage bucket is **private**. Files reachable only via short-lived presigned
      URLs generated after a permission check, with `Content-Disposition: attachment`.
- [ ] Uploads: whitelist `.pdf .jpg .jpeg .png`, 10 MB cap, randomized stored filenames,
      uploaded filename never trusted for paths.
- [ ] Dependabot enabled on the GitHub repository.
- [ ] Session expiry: 12 hours absolute, no idle timeout.
- [ ] Seed/fake data only in development. Real customer data never touches a laptop.

## Endpoint requirements for staff — mandate in writing before launch

The most likely breach is a staff laptop or Gmail account, not the application code. These
cost nothing and are worth more than any control in the software:

1. Full-disk encryption on (FileVault / BitLocker)
2. Automatic screen lock
3. A password manager; no reused passwords
4. No customer data stored in personal Drive, Downloads, or email

## Offboarding — same day, no exceptions

1. Admin **deactivates** the account (never deletes — the change history must survive)
2. Revoke Dropbox and any shared-drive access
3. Review that person's export log for the previous 30 days

## Backups

Three layers, because managed backups only protect against infrastructure failure:

1. Platform automatic daily backups with point-in-time recovery
2. Weekly encrypted dump to storage in a **different account**
3. Soft deletes only — nothing is ever hard-deleted, so human error is always recoverable

## Incident response — write this one-pager before launch

Texas requires notifying affected individuals after a breach, and notifying the Attorney
General within 30 days when more than 250 Texans are affected — which at 2,500 customers is
effectively guaranteed. The one-pager must name: who is called first, the attorney, the
cyber-liability carrier, the hosting provider's support path, and the notification
deadlines. An hour spent now is worth far more than an hour during an incident, when nobody
thinks clearly.

**Cyber liability insurance** is the correct control for residual risk that cannot be
engineered away. The agency sells insurance; this should be an easy conversation.

## Regulatory notes — verify with counsel before go-live

These are flagged from general knowledge and are **not** legal advice:

- **Texas HB 300** (Texas Medical Records Privacy Act) defines "covered entity" unusually
  broadly — broadly enough that a health-insurance agency handling coverage information may
  fall inside it, bringing employee training and breach-notification duties.
- **CMS** requires agents and brokers assisting with Marketplace applications to document
  consumer consent and retain that documentation for roughly ten years. This is the driver
  behind the Vault's indefinite-retention policy.
- **TCPA** creates a private right of action: $500 per message, $1,500 if willful. This is
  why SMS opt-out is enforced in code rather than by staff discipline (ADR-0009).

## Accepted risks

Deliberate omissions, each with an ADR. Recorded so a future maintainer knows they were
decisions, not oversights:

| Risk accepted | ADR |
|---|---|
| No application-level encryption of sensitive columns | ADR-0008 |
| No SMS consent capture; opt-out only | ADR-0009 |
| No logging of who *viewed* a record (only who changed it) | ADR-0010 |
| No virus scanning of uploaded files | ADR-0015 |
| No defense against a targeted, well-resourced attacker | this document |

## Review milestone

A security review pass is scheduled for **October 8, 2026**, a week before staff access.
A review with a date on the calendar happens; one that is "before launch" does not.
