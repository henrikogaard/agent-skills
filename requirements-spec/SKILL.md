---
name: requirements-spec
description: Use when turning needs, ideas, issues, product notes, bug reports, stakeholder requests, or analysis into a requirements specification with acceptance criteria, non-goals, edge cases, non-functional requirements, constraints, and a definition of done.
---

# Requirements Spec

Turn a clarified need into requirements that can guide design, implementation, and review. A good spec says what must be true without prematurely locking in how the solution is built.

## When To Use

Use this skill when:

- The user asks for requirements, acceptance criteria, scope, a spec, or a definition of done.
- A feature or fix needs user-visible criteria before design or implementation.
- Multiple people or agents need a shared contract for what "done" means.
- You need to convert analysis into something testable.

If the request is still unclear, use `needs-analysis` first. If the design approach is the main question, use `solution-design` after this skill.

## Workflow

1. Preserve source context: issue numbers, user request, screenshots, logs, constraints, and prior decisions.
2. Write the goal in outcome language.
3. Define in scope and out of scope.
4. Convert expectations into acceptance criteria that can be checked.
5. Add non-functional requirements when relevant: performance, accessibility, privacy, security, reliability, compatibility, observability, migration safety, and supportability.
6. List edge cases and failure states.
7. Define done in a way that connects to verification.

## Output Shape

Use this structure:

```markdown
Bottom line: [what this spec makes clear and what phase should follow].

Requirements

| Area | Requirement | Verification |
|---|---|---|
| Goal | Outcome, not implementation | User-visible check |
| In scope | Included behaviors or surfaces | Test, inspection, or QA |
| Out of scope | Explicit exclusions | No accidental implementation |
| Edge cases | Boundary/failure states | Focused tests or manual QA |
| Non-functional | Privacy, performance, security, a11y, compat | Specific check |
```

Then include:

```markdown
Acceptance criteria
1. [Behavior-level criterion]
2. [Behavior-level criterion]

Done means
- [Code/test/doc/release condition]
```

## Writing Rules

- Prefer behavior-level requirements over implementation tasks.
- Make criteria observable: a reviewer should know how to verify each one.
- Do not hide risky assumptions in broad words like "robust", "simple", or "works".
- Call out conflicts between requirements instead of smoothing them over.
- If requirements imply data migration, privacy, release, or design-system risk, route to the relevant guard skill.
- If `summary-tables` is available, use it for the main requirements matrix.
