---
name: issue-to-plan
description: Use when turning a GitHub issue, bug report, feature request, vague user request, product note, or investigation result into an executable engineering plan with acceptance criteria, scope, risks, sequencing, and verification targets.
---

# Issue To Plan

Convert incoming work into a plan that a senior engineer could execute without re-discovering intent.

## Required Shape

Start by preserving the user's goal and source references, such as issue numbers, links, quoted requirements, screenshots, or prior findings. Do not flatten away important details.

Produce these sections when relevant:

- Goal: one or two sentences describing the outcome.
- Scope: what is included and what is explicitly not included.
- Acceptance criteria: user-visible or behavior-level requirements.
- Change surface: likely backend, frontend, data, docs, infra, and test areas.
- Risks and unknowns: blockers, ambiguities, compatibility, security, data loss, migration risk.
- Plan: sequenced tasks with dependency order.
- Verification targets: commands, tests, browser/manual QA, and inspection points.
- Done means: what must be true before commit, PR, or handoff.

Use a compact table for plan items:

```markdown
| # | Plan item | Status |
|---|---|---|
| 1 | Define acceptance criteria from `#123` | Planned |
| 2 | Update persistence and API contract | Planned |
| 3 | Add focused tests and browser QA | Planned |
```

## Planning Rules

Prefer concrete work items over vague phases. "Add tests" is weak; "Add regression test for expired token rejection" is useful.

Flag missing decisions instead of guessing when the choice changes architecture, data retention, pricing, security, migration behavior, or user-visible semantics.

If the work is too large for one focused session, split it into staged plans and recommend the first slice.

Use `needs-analysis` first when the goal, user, constraint, or success condition is still unclear.

Use `requirements-spec` when acceptance criteria or done definition need to be made testable before planning implementation tasks.

Use `solution-design` when the plan depends on choosing between competing technical approaches.

If `summary-tables` is available, use it for the final table and status summary.
