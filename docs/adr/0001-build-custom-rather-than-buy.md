# ADR-0001: Build custom rather than buy

**Status:** Accepted — 2026-08-16

## Context

A three-person insurance agency with ~2,500 customers sits squarely inside the range where
off-the-shelf tools work. AgencyBloc, HubSpot, Airtable, and low-code builders all cover
most of the requirement. Custom software carries a permanent cost: every bug, dependency
upgrade, and hosting bill is owned forever by whoever maintains it.

The requirement was tested against that. The stated reasons for building are: the developer
wants control of the system, intends to add AI features in a later year, and is using the
project to learn software engineering.

## Decision

Build custom, and let the learning goal shape the design explicitly: **optimize for
comprehensibility and few moving parts**, not for scale, not for résumé value.

Every subsequent decision is judged against one test: *can one person debug this alone at
11pm?*

## Alternatives rejected

- **Off-the-shelf CRM** — cheaper and faster to launch, but forecloses the AI ambitions and
  the learning goal, and puts sensitive immigration and income data under someone else's
  control.
- **Low-code (Airtable, NocoDB, Budibase)** — nearly zero code, but per-seat pricing at
  three seats exceeds the budget, extension is awkward, and it teaches nothing transferable.

## Consequences

- The agency depends on one person's availability for at least two years. Mitigated by
  managed hosting, a conservative stack, and an admin-only data export so the agency is
  never hostage to the software (ADR-0002, ADR-0003).
- Features are justified against complexity cost, not against "a real CRM would have this."
- Scope discipline is a security control, not just a schedule control: less code is less
  attack surface for one person to review.
