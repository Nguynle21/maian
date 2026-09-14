# ADR-0003: Managed PaaS hosting in a US region

**Status:** Accepted — 2026-08-16

## Context

Staff must never manage servers. The budget is $20–50/month all in. The data is sensitive
enough that it must stay in US regions. The sole maintainer has limited operations
experience and an 8-week deadline.

## Decision

Deploy to a **managed platform (Render or Railway), US region**: managed web service plus
managed PostgreSQL with automatic backups and point-in-time recovery. Object storage on
Cloudflare R2. Nobody ever SSHes into anything.

Timezone: `America/Chicago`. The app is reachable at a normal public URL behind login, with
no IP allowlisting — allowlisting breaks the moment someone works from home.

## Alternatives rejected

- **A VPS (DigitalOcean, Hetzner).** Roughly $10/month cheaper, but the maintainer becomes
  responsible for OS patching, TLS renewal, and backup scripting. For a solo maintainer
  holding immigration and income data, saving $10/month by taking on that surface is a bad
  trade.
- **Serverless / edge.** More moving parts, worse fit for a long-running Django app,
  no benefit at three users.

## Consequences

- Predictable ~$15–35/month for compute and database.
- Backups and TLS are the platform's problem.
- Vendor lock-in is mild: Django and PostgreSQL move to any host.
- The platform is a trusted third party. Accepted; a breach at the provider is outside the
  threat model this project can defend against.
