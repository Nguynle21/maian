# ADR-0005: Application scoped to (Customer, Product, Plan Year)

**Status:** Accepted — 2026-08-16

## Context

In insurance the natural unit of work is the application, not the person. A customer holds
at most one active Health policy — switching plans terminates the old one — but may hold
Dental and Travel alongside it. Every customer files a new application each Open Enrollment.

Putting status on the Customer record collapses the moment someone holds two products, and
overwriting last year's data destroys the history the agency needs.

## Decision

`Application` is scoped to **`(Customer, Product, Plan Year)`**. A new row every year for
every product. Prior years are retained unchanged, forever.

`Product` is a database table seeded with Health, Dental, and Travel — editable by admin,
not a code enum. Things the business will plausibly change belong in data, not in code.

Any customer-level status is a **derived rollup** ("this customer needs attention because
one of their applications does"), never a stored field.

## Alternatives rejected

- **Status on the Customer.** Simplest possible model; breaks on the second product and
  loses all history.
- **Overwriting last year's application.** Saves rows; destroys the ability to compare years
  and makes the year-two roll-forward feature impossible.
- **Product as a Python enum.** One less table, but adding "Vision" would require a deploy.

## Consequences

- The database grows by ~2,500–3,000 rows a year. At that rate it is trivially small
  indefinitely; there is no reason to ever prune.
- "Roll forward last year's application into this year's" becomes the highest-value feature
  of the OE 2027 build — and is impossible in year one, since there is no prior year in the
  system. It must not creep into v1.
- The unique key `(customer, product, plan_year)` prevents accidental duplicate applications
  during the enrollment rush.
