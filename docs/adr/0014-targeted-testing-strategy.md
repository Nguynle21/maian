# ADR-0014: Test where silent failure is costly

**Status:** Accepted — 2026-08-16

## Context

Comprehensive test coverage is not achievable in eight weeks by a developer still learning
the language, and pursuing it would consume the schedule. Writing no tests at all leaves the
most dangerous logic unverified.

## Decision

Test **three things only**:

1. **The Application state machine** — every legal transition, and that every illegal one is
   rejected.
2. **The Send audience builder** — that an opted-out customer can never appear in a send
   queue, under any filter combination.
3. **Permissions** — that a Staff user cannot archive a record, manage users, or export.

Templates, forms, styling, and general view rendering are **not** tested.

## Reasoning worth preserving

The principle: **test where a silent failure is costly, not where a failure is obvious.**

A broken template is visible the moment someone loads the page — a test adds nothing a
glance would not catch. A state machine that permits an illegal transition, or a query that
quietly includes one opted-out customer in a thousand-message send, fails *silently* and
expensively. The first costs data integrity across a whole enrollment season; the second is
a TCPA claim (ADR-0009).

This also compensates for the main risk of AI-assisted development: AI writes plausible code
that passes review but is wrong about the domain. Tests on the state machine encode the
domain rules so a wrong change fails loudly.

## Consequences

- Coverage numbers will be low. That is intentional and not a defect.
- New business rules on the Application lifecycle come with a test. New screens do not.
- If a regression escapes into production, the response is to add a test for that specific
  failure — not to start a coverage initiative.
