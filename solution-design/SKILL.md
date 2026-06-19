---
name: solution-design
description: Use when choosing or documenting an implementation approach before coding, especially for architecture, design phase, tradeoffs, technical design, high-level design, low-level design, data flow, dependencies, rollout, alternatives, or pros and cons.
---

# Solution Design

Choose a practical design before implementation. Compare viable approaches, recommend one, and make the architecture, dependencies, tradeoffs, and verification implications explicit.

## When To Use

Use this skill when:

- The user asks for design, architecture, pros/cons, high-level design, low-level design, or approach selection.
- Requirements exist but the implementation path is still open.
- The change touches multiple modules, data flow, external services, UI state, infrastructure, or release behavior.
- A decision should be documented before coding.

Use `requirements-spec` first when "what must be true" is still unclear. Use `architecture-diagrams` when the design would benefit from Mermaid diagrams in `README.md`, `ARCHITECTURE.md`, ADRs, or design docs.

## Workflow

1. Restate the design goal and constraints.
2. Inspect the existing project structure and patterns before proposing new abstractions.
3. Present 2-3 plausible approaches with tradeoffs.
4. Recommend one approach and explain why.
5. Describe components, contracts, data flow, state, failure handling, and rollout.
6. Identify tests, docs, migration, privacy, release, and operational follow-up.
7. Mark open decisions that block implementation.

## Output Shape

Start with a direct recommendation:

```markdown
Recommendation: [approach name] because [short reason].

Options

| Option | Pros | Cons | Recommendation |
|---|---|---|---|
| Minimal patch | Fast, low churn | Leaves duplication | Use only if scope is tiny |
| Focused refactor | Better boundary, testable | Slightly more work | Recommended |
| Larger redesign | Future-proof | Too much for now | Defer |
```

Then include:

```markdown
Selected design
- Components:
- Data/control flow:
- Contracts:
- Error and edge handling:
- Rollout/rollback:
- Verification:
- Docs:
```

## Design Rules

- Match existing project patterns unless there is a concrete reason to change them.
- Keep boundaries small enough to understand and test.
- Avoid speculative architecture that does not serve the current requirement.
- Prefer reversible, staged changes when risk is high.
- Name external parties, storage, background jobs, auth boundaries, and generated clients explicitly.
- If `summary-tables` is available, use it for options and tradeoffs.
