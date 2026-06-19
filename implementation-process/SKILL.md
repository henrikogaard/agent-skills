---
name: implementation-process
description: Use when coding or executing an approved plan, feature, fix, refactor, or design, especially when the user wants an implementation process, step-by-step build, disciplined coding workflow, checkpoints, tests, docs, or progress through a plan.
---

# Implementation Process

Execute a plan in small, verifiable slices. Keep the work grounded in the accepted requirements and design, while adapting when code reality reveals better constraints.

## When To Use

Use this skill when:

- Requirements and/or a design are known enough to start coding.
- The user asks to implement, build, code, execute a plan, or work through a feature.
- The task has enough surface area that checkpoints, tests, and docs matter.
- Multiple existing skills need to be sequenced during implementation.

If requirements are missing, use `requirements-spec`. If the approach is still undecided, use `solution-design`.

## Workflow

1. Reconfirm the target outcome, scope, and accepted assumptions.
2. Inspect relevant files before editing.
3. Break work into small slices with verification after each meaningful slice.
4. Use the repo's existing patterns and helpers.
5. Update tests close to the behavior being changed.
6. Keep docs, diagrams, release notes, and issue comments aligned as needed.
7. Before completion, run the right verification and review process.

## Implementation Table

Use a progress table for non-trivial work:

```markdown
Implementation plan

| # | Slice | Status | Verification |
|---|---|---|---|
| 1 | Update contract/type | Planned | Typecheck |
| 2 | Implement behavior | Planned | Focused tests |
| 3 | Update UI/docs | Planned | Browser/manual QA |
```

Update statuses as work progresses: `Planned`, `In progress`, `Done`, `Blocked`, or `Deferred`.

## Coordination

Use related skills when they fit:

- `change-surface-map` before touching broad or uncertain surfaces.
- `debugging-process` when the implementation starts from a failing test, regression, broken build, or unclear error.
- `verification-matrix` to choose tests and manual QA.
- `docs-sweep` when behavior, commands, architecture, release notes, or runbooks change.
- `privacy-local-first-review` for telemetry, auth, storage, credentials, sync, or external calls.
- `migration-safety` for database or data-shape changes.
- `review-before-commit` before publishing or declaring complete.
- `completion-handoff` for the final closeout.

## Rules

- Do not expand scope quietly. Put discovered cleanup into follow-up unless it is needed for the requested outcome.
- Do not claim completion without evidence from tests, builds, browser/manual QA, or explicit skipped-check notes.
- Prefer fixing visible issues encountered in touched code over leaving known regressions.
- Protect unrelated local changes and use `safe-git-handoff` before staging or committing.
- If `summary-tables` is available, use it for progress and final implementation readouts.
