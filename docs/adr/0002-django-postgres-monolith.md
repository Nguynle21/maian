# ADR-0002: Django + PostgreSQL, server-rendered monolith

**Status:** Accepted — 2026-08-16

## Context

The application is CRUD-heavy and form-heavy: three concurrent users, ~2,500 records,
role-based permissions, a heavy seasonal data-entry burst, and a Python-shaped future (AI).
There is no requirement for a rich interactive UI, real-time collaboration, mobile apps, or
scale.

The developer has solid SQL, Python foundations without fluent syntax, strong product and
system-design instincts, and works with AI assistance. They maintain it alone for two years,
then hand off to a non-technical staff member.

## Decision

**Django + PostgreSQL, server-rendered, one deployable.** HTMX for interactivity where a
page reload is not enough. S3-compatible object storage (Cloudflare R2) for documents.

Django's admin is the maintainer's escape hatch and the handoff artifact — **not** the staff
UI. Staff get a purpose-built intake form and worklist, because ACA intake is too specific
for a generic admin.

## Alternatives rejected

- **Next.js + Supabase.** Genuinely competitive: more AI training data behind it, and
  Supabase's auth and storage would cover login and the Vault with almost no code. Rejected
  because it trades a small win in code generation for a large loss in concepts the sole
  maintainer must personally understand — React state, hydration, server vs. client
  components — and because row-level security fails *silently* when written wrong.
- **FastAPI + HTMX.** Lighter, but auth, permissions, forms, and admin would all be
  hand-built. That is exactly the work Django removes.
- **Rails.** Equivalent in shape; the developer does not know Ruby.

## Reasoning worth preserving

The decisive question was not "which stack is best" but **"which stack gives the most for
free in exactly the areas the developer is weakest."** The developer is strong at data
modeling and weak at writing code. Django hands over auth, permissions (which map exactly
onto Admin/Staff roles), form validation, migrations, and a working admin panel, leaving
effort for the schema and workflow.

A second, counterintuitive point: under AI-assisted development, what matters is not how
much code the AI can generate but **how much code has to exist for it to be wrong about.**
Django requires less code for the same features, so there is less surface for subtle errors.

Learning-optimal and system-optimal converge here. Django would still be the recommendation
for a developer who already knew React.

## Consequences

- One language to hold in mind (plus HTML and a little JavaScript).
- The maintainer must personally understand the **schema and the state machine**; being
  fuzzy on templates, views, and CSS is acceptable. Schema errors compound and are expensive
  to unwind; a bad template is a ten-minute fix. AI cannot tell you when it is wrong about
  *your* domain.
- Python is also the right ecosystem for the later AI work.
