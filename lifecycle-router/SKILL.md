---
name: lifecycle-router
description: Use when the user asks to build, fix, plan, design, review, ship, improve, or work through a project lifecycle and the right phase is not explicit. Routes work through needs analysis, requirements, solution design, implementation, verification, review, docs, and handoff without over-gating simple tasks.
---

# Lifecycle Router

Choose the right lifecycle phase before acting. This skill keeps work from jumping straight to code when analysis, requirements, or design are still needed, while still allowing simple clear tasks to move quickly.

## Phase Routing

Classify the current request:

| Signal | Phase | Use |
|---|---|---|
| Vague idea, broad goal, "what should we do", unclear user/value | Needs | `needs-analysis` |
| Need acceptance criteria, scope, done definition, edge cases | Requirements | `requirements-spec` |
| Need architecture, approach choice, pros/cons, high/low-level design | Design | `solution-design` |
| Approved or obvious plan, user asks to build/code/fix | Implementation | `implementation-process` |
| Failing test, broken build, regression, crash, flaky behavior, unclear error | Debugging | `debugging-process` |
| Need test strategy, evidence, readiness, QA | Verification | `verification-matrix` |
| Before commit, PR, push, or "is this ready?" | Review | `review-before-commit` and `safe-git-handoff` |
| Need docs, diagrams, README, ADR, release notes | Documentation | `docs-sweep` or `architecture-diagrams` |
| Need final status, what changed, remaining work | Handoff | `completion-handoff` and `summary-tables` |

## Workflow

1. Identify the phase from the user's words and available context.
2. Check whether enough information exists to enter that phase.
3. If not, route one phase earlier and ask at most one blocking question.
4. If the request is small and clear, proceed without ceremony.
5. For larger work, name the lifecycle path before acting.

## Output Shape

When routing is useful, use:

```markdown
Lifecycle route

| Phase | Status | Why |
|---|---|---|
| Needs | Done/Needed/Skipped | Evidence |
| Requirements | Done/Needed/Skipped | Evidence |
| Design | Done/Needed/Skipped | Evidence |
| Implementation | Ready/Blocked | Evidence |
| Review | Pending | Evidence |
```

Then state the next action:

```markdown
Next: use `requirements-spec` to make the acceptance criteria testable before design.
```

## Default Paths

- New feature: `needs-analysis` -> `requirements-spec` -> `solution-design` -> `implementation-process` -> `verification-matrix` -> `review-before-commit` -> `completion-handoff`.
- Bug fix: `needs-analysis` if unclear -> `change-surface-map` -> `requirements-spec` for expected behavior -> `implementation-process` -> `verification-matrix` -> `review-before-commit`.
- Failing test or regression: `debugging-process` -> `verification-matrix` -> `review-before-commit` -> `completion-handoff`.
- Small mechanical edit: implement directly -> verify -> `completion-handoff`.
- Architecture/doc task: `solution-design` -> `architecture-diagrams` -> `docs-sweep` -> `summary-tables`.

## Rules

- Do not use lifecycle phases as bureaucracy. Use the minimum structure that prevents rework.
- Do not block implementation for approval when the user explicitly asks for a clear small change.
- Do not skip requirements or design when missing decisions would change data, security, privacy, release, UX, or architecture.
- Preserve momentum: if you can make a safe assumption, state it and continue.
- If `summary-tables` is available, use it for phase and readiness summaries.
