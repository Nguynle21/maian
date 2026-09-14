# Scope and Timeline

## The deadline that governs everything

Open Enrollment opens **November 1, 2026**. During those ten weeks staff touch every one of
the ~2,500 customers anyway — which makes Open Enrollment the natural migration window.
Entering customers into the new system *is* the migration. Miss the window and the project
slips a full year.

| Date | Milestone |
|---|---|
| **Oct 8, 2026** | Security review pass over finished code (`/security-review` + manual checklist) |
| **Oct 15, 2026** | Ship to staff. Each enters 10–20 real customers. Fix what the workflow reveals. |
| **Nov 1, 2026** | Hard cutover. Dropbox becomes read-only reference. No dual entry. |
| Nov 2026 – Jan 2027 | Open Enrollment. System in anger. |
| Dec 2026 – Feb 2027 | Phase 2 features ship as capacity allows |
| ~Mar 2027 | Enrollment work winds down |

The working deadline is **October 15**, not November 1.

> **Revised 2026-09-13.** Staff now enter current (2026) Customer data as soon as possible,
> and an October Send asks Customers to call back for 2027 enrollment. SMS moves into
> Phase 1; build order is intake → Send → Worklist; autosave and export are deferred. See
> `docs/superpowers/specs/2026-09-13-intake-and-send-design.md`. The sections below are the
> original plan, kept for reasoning.

## Phase 1 — must ship by Oct 15

- Login: email + password + mandatory 2FA, accounts created by admin, no self-signup
- Two roles: Admin and Staff
- Customer intake form — one long page, collapsible sections, conditional fields, autosave draft
- Customer library: search by name, both phone numbers, and DOB; duplicate warning at entry
- Applications: `(customer, product, plan year)`, Stage, Payment Status, Docs Due On
- Worklist home screen with filtered buckets
- Application event history (who changed what, when)
- Minimal Vault: upload, list, download, admin-only archive. Nothing more.
- Admin-only Excel/CSV export, logged
- Soft delete throughout

## Phase 2 — Dec 2026 to Feb 2027

- Twilio SMS: free-text compose, placeholders, audience filter by `preferred_language`,
  review queue, segment counter and cost estimate, 100-message cap on the first send
- STOP handling → opt-out flag → worklist bucket
- Vault polish: tagging, retention markers
- Daily email digest, *only if* staff turn out not to log in daily

## Later years

Roll-forward of last year's application (the highest-value OE 2027 feature), e-signature,
structured policy fields, commission tracking, AI.

## Cut lines, stated in advance

If the schedule slips, cut in this order: Excel export → Vault → duplicate warning →
event history. Never cut: the intake form, search, Application status, or the worklist.
Those four are Open Enrollment.

## Migration

No automated import. Staff re-enter from the existing Excel-on-Dropbox files by hand as a
deliberate fresh start — the existing data is messy and full of information the new system
should not carry forward. The re-entry happens naturally as staff process each customer's
enrollment.

The risk this accepts: for the first weeks of OE the two systems disagree, and any customer
not yet touched exists only in Dropbox. Mitigated by the hard cutover date and by the fact
that OE forces every customer to be touched within ten weeks.

## Rollout to staff

Three non-technical people switching tools on the first day of their busiest season is the
main non-technical risk in this project. Mitigations: two weeks of early access with real
data, a written one-page how-to, and no dual-running after November 1.

## Budget

Target $20–50/month all-in.

| Item | Approx. monthly |
|---|---|
| Web service (managed PaaS) | $7–15 |
| Managed PostgreSQL with backups | $7–20 |
| Cloudflare R2 object storage | ~$0–1 at this volume |
| Twilio A2P 10DLC campaign | ~$2–4 |
| SMS traffic | metered, bursty |

**Two costs that surprise people.** US SMS requires A2P 10DLC brand and campaign
registration with Twilio — a one-time brand fee, a small monthly campaign fee, and
days-to-weeks of approval time. Start registration well before the first send, not the week
of. And Vietnamese diacritics fall outside the GSM character set, so those messages encode
as UCS-2 at **70 characters per segment instead of 160** — a Vietnamese message can cost
2–3× the English equivalent. The compose screen must show segment count and estimated cost
before sending.

*(Verify current Twilio pricing and CMS/TCPA requirements before launch; figures here are
directional.)*
