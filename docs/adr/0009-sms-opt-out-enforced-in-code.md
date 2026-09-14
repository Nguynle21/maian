# ADR-0009: No SMS consent capture; opt-out enforced in code

**Status:** Accepted — 2026-08-16
**Type:** Accepted risk

## Context

The agency sends bulk SMS — birthday greetings, and reminders asking customers to call and
update their information. Roughly 1,000 primary phone numbers, sent occasionally, never
monthly to everyone.

The US TCPA creates a **private right of action**: $500 per message, $1,500 if a court finds
it willful. It is not a government fine — the recipient sues. Texting someone five times
after they opted out is a $2,500–$7,500 claim from a single person.

An opt-in consent checkbox on the intake form was proposed and declined: it adds data entry
to a form staff will fill 2,500 times.

## Decision

**No consent capture on the intake form.** Instead:

- A single `sms_opt_out` boolean per Customer, defaulting to false
- Flipped automatically when Twilio reports a **STOP**
- **Every Send excludes opted-out customers in code**, not by staff discipline
- Opt-outs surface as a worklist bucket ("Opted out — needs a call") so staff can follow up
  by phone, per the agency's request

## Reasoning worth preserving

The design principle here generalizes: **make the dangerous thing impossible rather than
discouraged.** A rule that a tired staff member must remember at 6pm in December is not a
control. A filter in the query is.

## Alternatives rejected

- **Opt-in consent checkbox on the intake form.** Strictly safer legally. Declined for data
  entry cost. Can be added later during the OE conversation the agency is already having
  with every customer, at near-zero marginal cost.
- **Trusting staff to exclude opt-outs manually.** Not a control.

## Consequences

- The agency can prove it honored every opt-out, which is the most common TCPA claim.
- It cannot prove affirmative consent for the *first* message to any given customer. That
  residual exposure is accepted, and is a reason to carry cyber liability insurance.
- Additional send-safety measures: a segment counter and cost estimate before sending, a
  review queue requiring a human click, and a 100-message cap on the first ever send so a
  mistake costs $1 rather than $50.
