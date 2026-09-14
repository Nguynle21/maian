# Maian

An internal CRM for a 3-person health-insurance agency in Missouri City, Texas, serving
~2,500 ACA Marketplace customers. Read `CONTEXT.md` before touching anything.

## Read these first

- **`CONTEXT.md`** — domain model and glossary. Use its vocabulary exactly; do not drift to
  synonyms it avoids ("client", "lead", "delete", "campaign").
- **`docs/adr/`** — every architectural decision with its rejected alternatives. Read the
  ADRs covering the area you are about to work in.
- **`docs/scope-and-timeline.md`** — what ships when.
- **`docs/security-baseline.md`** — required configuration and accepted risks.

If your work contradicts an ADR, **say so explicitly** rather than silently overriding it:
> _Contradicts ADR-0007 (unstructured policy details) — but worth reopening because…_

## The governing constraint

One person maintains this alone for two years, then hands it to a non-technical staff
member. Every choice is judged by: **can one person debug this alone at 11pm?**

Optimize for comprehensibility and few moving parts. Not for scale, not for elegance, not
for what a larger system would do. Fewer dependencies beats more features.

## Fixed decisions — do not propose alternatives

| | |
|---|---|
| Stack | Django + PostgreSQL, server-rendered, one deployable (ADR-0002) |
| Interactivity | HTMX. No React, no SPA, no separate frontend build |
| Hosting | Managed PaaS (Render/Railway), US region, `America/Chicago` (ADR-0003) |
| Files | Cloudflare R2, private bucket, presigned URLs (ADR-0007) |
| Auth | Email + password + mandatory 2FA, admin-created accounts (ADR-0012) |
| Roles | Admin and Staff. Both see all customers; only Admin archives, exports, manages users |
| Environments | Local and production only. No staging (ADR-0013) |
| SMS | Twilio |

Do not introduce a new service, queue, cache, container orchestrator, or frontend framework.
If something seems to need one, say so and explain why before writing code.

## Domain rules that must not be broken

- **`Application` is scoped to `(Customer, Product, Plan Year)`.** Never put enrollment
  status on `Customer`. Customer-level status is always derived, never stored. (ADR-0005)
- **`stage` and `payment_status` are separate fields.** Never merge them into one enum.
  Payment can be missing at any stage. (ADR-0004)
- **`ApplicationEvent` is append-only.** Never update or delete an event row.
- **Nothing is hard-deleted.** Soft delete via `archived_at`, filtered at the model manager
  level. Say "archive", never "delete". (ADR-0011)
- **Opted-out customers are excluded from sends in code**, never by staff discipline.
  (ADR-0009)
- **No SSNs, no card numbers.** Ever. If a requirement seems to need one, stop and ask.
- **Almost every field is nullable.** Real intake is interrupted; a form that refuses to
  save incomplete data gets defeated by staff typing "N/A". Enforce completeness with a
  visible checklist on the record, not a blocked Save button.

## Out of scope

Customer-facing anything, e-signature, commission tracking, accounting, carrier-portal
integration, AI features, mobile/native apps, offline mode, and rolling last year's
application forward. Do not build these, and do not add abstractions in anticipation of
them.

## Security — non-negotiable

Before any deploy, the checklist in `docs/security-baseline.md` applies. In particular:
`DEBUG=False`, secrets only in environment variables, private bucket, `.gitignore` from the
first commit.

**Never put real customer data on a development machine.** Develop against the seed script.

## Testing

Test the Application state machine, the send audience builder, and permissions. Nothing
else. Test where silent failure is costly, not where failure is obvious. (ADR-0014)

## Agent skills

### Issue tracker

Issues live in GitHub Issues for `Nguynle21/maian` (uses the `gh` CLI). See
`docs/agents/issue-tracker.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
