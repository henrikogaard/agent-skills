---
name: pr-description
description: Use when drafting, updating, or reviewing a pull request description, merge request body, release-facing change summary, or reviewer guide that needs context, changes, tests, risks, screenshots, and linked issues.
---

# PR Description

Write PR bodies that help reviewers understand intent, inspect risk, and verify behavior quickly.

## Gather Inputs

Use the issue, plan, diff, commits, tests, screenshots, logs, and user notes. Preserve exact issue numbers, branch names, commands, and notable files.

## Template

```markdown
## Summary
- What changed and why.

## Changes
- Backend/API/data changes.
- Frontend/UI/workflow changes.
- Docs, migrations, tooling, or generated artifacts.

## Verification
- `command` - result
- Browser/manual QA target - result

## Risk / Rollback
- Main risk and mitigation.
- Rollback or follow-up note.

## Reviewer Notes
- Files or flows worth reviewing first.
- Known leftovers or intentionally deferred work.
```

Add screenshots or screen recordings only when UI changed and assets are available.

## Rules

Do not invent verification. If a check was not run, say "Not run" and why.

Do not hide risk. Reviewers trust PRs that clearly name sharp edges.

Keep the body concise, but include enough detail that a reviewer can reproduce the important checks.

If `completion-handoff` or `summary-tables` is available, use them to preserve evidence and structure.
