# Design: Intake, Vault, and Send (build order revised)

**Date:** 2026-09-13
**Status:** Approved in conversation, 2026-09-13

## Why the plan changed

The original plan (`docs/scope-and-timeline.md`) had staff re-enter Customers during Open
Enrollment and put SMS in Phase 2. The agency now wants to:

1. Have staff enter every Customer's **current (2026) information** as soon as possible.
2. In **October**, send a bulk SMS asking Customers to call back and update their
   information for the 2027 enrollment.
3. Run Open Enrollment from Nov 1 on the Worklist, as originally planned.

That makes Send a pre-OE feature and turns re-entry into its own effort before OE.

### Decisions this contradicts

- **ADR-0006 (manual re-entry during OE):** re-entry is now a separate ~165-hour effort
  before OE, not a by-product of OE work. Customers not entered by send day do not receive
  the October reminder. Accepted by the agency.
- **`docs/scope-and-timeline.md`:** SMS moves from Phase 2 to Phase 1, and the build order is
  now intake → Send → Worklist. The document is updated alongside this spec.
- **`docs/security-baseline.md` review milestone:** real customer data enters production
  before the Oct 8 review. The **required-configuration checklist must pass in production
  before the first real Customer is saved**. The full review stays on Oct 8.
- **Scope doc, "autosave draft":** cut for now. Save never refuses incomplete data, which
  removes most of autosave's value. Revisit if staff lose work.
- **CONTEXT.md, "Dependents carry a CHIP/Medicaid flag":** replaced by `public_coverage`,
  because dependents include elderly parents on Medicare. CONTEXT.md is updated.

## Build order

| Step | Contents | Gate to ship |
|---|---|---|
| 1 | Foundation, auth + 2FA, roles, Customer + Household Member, intake form, search, duplicate warning, minimal Vault | Security checklist passes in production |
| 2 | Send: compose, audience, review, batched sending, STOP/START webhook | Twilio A2P 10DLC approved |
| 3 | Product, Plan Year, Application, ApplicationEvent, state machine, Worklist | Before Nov 1; designed separately |

Deferred: Excel/CSV export (first on the cut list; Admin uses Django admin meanwhile),
autosave.

## Data model (step 1)

Every field below is nullable/blank-able unless marked. Every model with `archived_at` uses a
default manager that excludes archived rows (ADR-0011).

### Customer

| Field | Type | Notes |
|---|---|---|
| first_name, middle_name, last_name | text | |
| gender | choice: female, male | |
| date_of_birth | date | |
| email | email | |
| res_street, res_apt, res_city, res_state, res_zip | text | `res_state` defaults to `TX` |
| mailing_same_as_residential | bool, default true | mailing fields ignored when true |
| mail_street, mail_apt, mail_city, mail_state, mail_zip | text | |
| phone_primary, phone_secondary | text | stored as 10 digits; the form accepts any format |
| emergency_contact_name, emergency_contact_phone | text | phone normalized as above |
| preferred_language | choice: en, vi, es | |
| immigration_status | choice: us_citizen, green_card, visa, work_permit | |
| household_income | integer, annual USD | |
| sms_opt_out | bool, default false, **not null** | never on the intake form; set only by the Twilio webhook |
| sms_opt_out_at | datetime | |
| created_at, updated_at | datetime, not null | |
| created_by | FK User | |
| archived_at | datetime | |

### HouseholdMember

| Field | Type | Notes |
|---|---|---|
| customer | FK Customer, **not null** | |
| relationship | choice: spouse, dependent, **not null** | |
| first_name, middle_name, last_name | text | |
| gender | choice | |
| date_of_birth | date | |
| phone | text | normalized |
| immigration_status | choice | shown for spouse only |
| public_coverage | choice: none, chip, medicaid, medicare | shown for dependent only |
| linked_customer | FK Customer | set when the member gets their own Customer record |
| archived_at | datetime | |

### VaultDocument

| Field | Type | Notes |
|---|---|---|
| customer | FK Customer, not null | |
| storage_key | text, not null | random UUID-based key; the uploaded name is never used in the path |
| original_filename | text | shown in the UI only |
| content_type, size_bytes | | |
| uploaded_by, uploaded_at | | |
| archived_at, archived_by | | Admin only |

### AuditEvent (ADR-0010)

An append-only record of archive, restore, and user-management actions: who, when, action,
target type, target id. (Export events join it when export ships.) `ApplicationEvent` stays
separate and arrives in step 3.

## Step 1 behaviour

**Auth.** `django-two-factor-auth` (TOTP authenticator app plus backup codes). Every view
except login requires a verified 2FA session. `django-axes` locks out after 5 failures.
Sessions last 12 hours with no idle timeout. There is no signup; Admin creates users in Django
admin. Roles are Django groups `Admin` and `Staff`. Django admin lives at a non-default path
taken from an environment variable.

**Intake form.** One page, sections that collapse without JavaScript (`<details>`):
Customer → Spouse (0–1) → Dependents (0–n, "add another" via HTMX) → Vault upload. One Save
button, which always succeeds. The Customer record page shows a **completeness checklist**
(missing DOB, missing primary phone, missing preferred language, etc.).

**Duplicate warning.** Shown while the form is being filled (HTMX on blur) and again on the
record page. A possible duplicate is an existing, non-archived Customer where a normalized
phone matches any phone on the form, or where last name + DOB match. It never blocks Save.

**Search.** One box. Digits are matched against both phone numbers. A date is matched against
DOB. Anything else is matched case-insensitively against first and last name. Accent-
insensitive matching for Vietnamese names uses PostgreSQL `unaccent`.

**Vault.** Upload from the form or the record page. Accepted: `.pdf .jpg .jpeg .png`, 10 MB
max. Files are stored in the private R2 bucket. Downloads go through a view that checks login
and then redirects to a 5-minute presigned URL with `Content-Disposition: attachment`. Only
Admin can archive.

**Archive.** Admin-only, for Customers, Household Members, and Vault Documents. It is logged
to `AuditEvent`, and restore is available in Django admin.

## Step 2: Send

**Models.**
- `Send`: body, language filter, created_by, created_at, status (`draft` → `sending` →
  `done`), recipient_count, estimated_segments.
- `SendRecipient`: send FK, customer FK, phone (snapshot), rendered_body, status
  (`pending` | `sent` | `failed`), twilio_sid, error, sent_at. There is a unique constraint on
  `(send, customer)`.

**Audience builder.** One function, `build_audience(language=None)`, is the only way
recipients are chosen. It always excludes `sms_opt_out=True`, archived Customers, and
Customers without `phone_primary`. There is no parameter that turns these exclusions off.
It returns **one recipient per phone number** (the oldest Customer record wins), so a shared
household phone gets one text. If **any** Customer on a number has opted out, the number is
excluded entirely.
**Tested** under every filter combination (ADR-0014).

**Compose.** Free text with `{first_name}` as the placeholder; a blank name renders as an
empty string with whitespace tidied. A live counter shows characters, encoding (GSM-7 vs
UCS-2), segments per message, and estimated total cost. The per-segment price is a setting.

**Review.** Shows the recipient count, total segments, estimated cost, three sample rendered
messages, and a list of recipients. **Nothing is sent without a click on this screen.** If no
Send has ever reached `done`, the audience is capped at 100 and the screen says so.

**Sending.** Confirming creates every `SendRecipient` row in one transaction and sets the Send
to `sending`. The progress page repeatedly POSTs `/sends/<id>/batch` (HTMX), and each request
sends the next 25 `pending` rows. Rows are claimed with `SELECT … FOR UPDATE SKIP LOCKED` and
marked `sent` or `failed` right after their Twilio call. Closing the tab pauses sending, and
reopening the page resumes it. A row marked `sent` is never retried. The opt-out flag is
**re-checked at send time**, so a Customer who replies STOP mid-send is skipped.

**Webhook.** `POST /twilio/inbound` validates the Twilio signature and rejects anything
invalid. `STOP`, `STOPALL`, `UNSUBSCRIBE`, `CANCEL`, `END` and `QUIT` set `sms_opt_out` on
every Customer whose `phone_primary` matches. `START`, `UNSTOP` and `YES` clear it. Both are
logged to `AuditEvent`. Twilio's own Advanced Opt-Out also refuses delivery to a STOPped
number (error 21610), which is a second net under our flag, not a replacement for it.

## Error handling

- A Twilio failure on one recipient marks that row `failed` with the error text, and sending
  continues. The Send's done page lists the failures.
- An R2 upload failure shows an error on the form; the Customer's other data still saves.
- Production runs with `DEBUG=False`, and errors go to the platform log.

## Testing (ADR-0014 only)

- The audience builder never returns an opted-out, archived, or phone-less Customer, under any
  filter. The batch sender skips a Customer who opted out after the queue was built.
- The webhook rejects bad signatures, and STOP/START flip the flag.
- Staff cannot archive Customers, Household Members, or Vault Documents, and cannot open
  Django admin at all (only Admin users have `is_staff`).
- The state machine is tested in step 3.

## Project layout

```
maian/            settings, urls, wsgi
customers/        Customer, HouseholdMember, intake form, search, duplicates
vault/            VaultDocument, upload/download
sends/            Send, SendRecipient, audience, compose/review/batch, webhook
core/             AuditEvent, roles, archive manager, base templates
templates/, static/  plain CSS, vendored htmx.min.js (no build step)
```

Dependencies: Django, psycopg, django-two-factor-auth, django-axes, boto3, twilio,
whitenoise, gunicorn, dj-database-url. Nothing else.

## Outside-the-code setup (user)

1. **Today:** Twilio account → A2P 10DLC Brand + Campaign → local number.
2. **Before step 1 ships:** Render (web service + PostgreSQL, US region), Cloudflare R2
   private bucket + API token, environment variables, custom domain optional.
