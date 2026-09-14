# ADR-0013: Two environments, no staging

**Status:** Accepted — 2026-08-16

## Context

The conventional setup is local → staging → production. For a solo maintainer with an
eight-week deadline, staging is a third environment to keep in sync, pay for, and remember
to migrate.

## Decision

**Two environments: local and production.** Git on GitHub, deploy from `main`.

A **seed script generates ~200 fake customers** so development happens against realistic
volume — and so that **real customer data never touches the maintainer's laptop.**

## Alternatives rejected

- **A staging environment.** Correct at larger scale and for teams. Here it doubles the
  infrastructure cost, adds a synchronization burden, and would most likely drift out of
  date and be ignored — which is worse than not having one.
- **Developing against a copy of production data.** Convenient and the single largest
  avoidable increase in breach exposure: it puts 2,500 people's immigration status on a
  laptop that leaves the office.

## Consequences

- Migrations are exercised for the first time in production. Mitigation: PostgreSQL
  backups with point-in-time recovery, and migrations reviewed before deploy.
- The seed script must stay realistic — a mix of Vietnamese and English names, messy phone
  formats, missing DOBs, and duplicate-looking people — or bugs that only appear with real
  data will not surface until November.
- Never storing real data locally is a hard rule, not a preference.
- If a team ever forms, add staging then. This ADR is scoped to the solo period.
