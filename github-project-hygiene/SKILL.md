---
name: github-project-hygiene
description: Use when checking, reconciling, or updating GitHub issues, project-board Status fields, labels, comments, QA handoff state, stale issue notes, closeout readiness, or issue implementation status across Henrik's repositories.
---

# GitHub Project Hygiene

Keep GitHub issue state, project-board status, labels, comments, and implementation reality aligned. The board should show what is actually true, not what an agent hopes is true.

## When To Use

Use this skill for:

- Moving issues between `Backlog`, `Ready`, `In progress`, `In review`, and `Done`.
- Checking whether issues are implemented, partial, stale, blocked, or ready for QA.
- Updating issue comments after implementation.
- Reconciling labels with project status.
- Auditing stale issue comments or board drift.
- Preparing closeout recommendations.

## Status Semantics

Respect repo-level definitions first. In Henrik's repos, the usual pattern is:

| Status | Meaning |
|---|---|
| `Backlog` / `Open` | Captured idea or accepted work needing more shaping |
| `Ready` | Scoped enough for implementation |
| `In progress` | Agent or human is actively working |
| `In review` | Implementation is ready for Henrik QA |
| `Done` | Henrik confirmed QA/signoff and requested closeout |

Do not close issues or move them to `Done` without explicit user confirmation unless the repo instructions say otherwise.

## Reconciliation Flow

1. Read the repo `AGENTS.md` for board and label rules.
2. Read the issue body, comments, linked PRs, and acceptance criteria.
3. Check code/docs/git state before assuming implementation status.
4. Classify each issue: implemented, partial, not started, blocked, stale-comment, or ready-to-close.
5. Update board status and labels only when allowed by the repo rules and user request.
6. Add a concise issue comment when implementation, verification, or remaining work changed.
7. Report exact actions taken and recommended actions that still need Henrik approval.

## Drift Checks

Look for:

- Closed issues not in `Done`.
- `In review` issues without a QA handoff comment.
- `Ready` issues that are actually implemented.
- `status:qa` labels missing project-board `In review`.
- Stale comments that contradict current constants, commits, or verification.
- Parent issues moved forward while child work is incomplete.

## Output Shape

Use grouped tables:

```markdown
Implemented on `development`

| Issue | Status | Action |
|---|---|---|
| `#340` | Complete, comment stale | Corrected comment; keep `In review` |

Needs Henrik signoff

| Issue | Recommendation | Why |
|---|---|---|
| `#333` | Close + move `Done` | QA confirmed in latest comment |
```

## Rules

- Never treat labels as the source of truth when the repo says project `Status` is authoritative.
- Never hide uncertainty; if implementation status was not checked against code, say so.
- Prefer recommendations over destructive state changes when Henrik has not explicitly approved closeout.
- If `summary-tables` is available, use it for the final status readout.
