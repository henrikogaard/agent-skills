---
name: completion-handoff
description: Use when finishing implementation, committing, pushing, opening or updating a PR, moving an issue, or handing work back to the user with shipped changes, verification, leftovers, risks, and exact next steps.
---

# Completion Handoff

Finish work with an evidence-backed handoff that preserves operational details. The user should know what changed, what was verified, what was not touched, and what to do next.

## Required Content

Include the sections that match the work:

- What shipped: changed behavior, files, components, migrations, docs, routes, generated artifacts.
- What is working: user-visible behavior and important internal contracts.
- Verification: exact commands, test counts, browser/manual QA, skipped checks with reasons.
- Commit and publish state: commit SHA, branch, remote, PR, issue status, labels, project state, posted comments.
- Left out: unrelated local changes, generated artifacts, deferred work, known risks.
- Next step: one concrete recommendation or pickup instruction.

Use a table when summarizing several items:

```markdown
| # | Handoff item | Status |
|---|---|---|
| 1 | Backend persistence and API contract | Done: `Service.cs`, `Dto.ts`, migration |
| 2 | Focused test suite | Done: `45 passed` |
| 3 | Manual browser QA | Not run: needs interactive desktop session |
```

## Rules

Do not say "done" without verification status. If verification was not run, say exactly why.

Do not omit local leftovers. Users need to know what was intentionally excluded from a commit or PR.

If commit/push happened, include the short SHA and destination. If not, say "not committed" or "not pushed" directly.

If `summary-tables` is available, use it for the final structure.

