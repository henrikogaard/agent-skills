---
name: review-before-commit
description: Use before committing, pushing, opening a PR, or declaring implementation complete when a final bug, regression, security, data-loss, behavior, or missing-test review of local changes is needed.
---

# Review Before Commit

Take a code-review stance before publishing work. Prioritize bugs, regressions, missing verification, security issues, data-loss risks, and accidental unrelated changes.

## Review Inputs

Inspect the diff, staged state, test results, and worktree status. For Git repos, prefer:

```bash
git status --short
git diff --stat
git diff
git diff --cached
```

Use focused file reads when the diff depends on surrounding code.

## Findings Format

Lead with findings, ordered by severity:

```markdown
Findings:
1. High: title
   `path/file.ext:123` explanation, impact, and fix.
2. Medium: title
   `path/file.ext:45` explanation, impact, and fix.
```

If there are no findings, say that clearly and list residual risk or test gaps.

## Review Checklist

- Behavior matches the request and acceptance criteria.
- No unrelated changes, debug code, secrets, generated clutter, or accidental formatting churn.
- Error states, permission checks, boundary cases, and concurrency/timing cases are handled.
- Data migrations are compatible and avoid silent data loss.
- Tests cover the changed behavior and denial/error paths where relevant.
- Docs, issue comments, worklog, and PR body match the actual change.

## Related Reviews

Use the focused guard skills when the diff touches their surface:

| Surface | Use |
|---|---|
| Test strategy or missing QA evidence | `verification-matrix` |
| Telemetry, auth, secrets, external calls, storage, or sync | `privacy-local-first-review` |
| Migrations, indexes, backfills, constraints, or data corrections | `migration-safety` |
| Versions, changelogs, release notes, tags, updater manifests, or deploy steps | `release-surface-guard` |
| Staging, committing, pushing, unrelated changes, or worktree state | `safe-git-handoff` |

## Rules

Do not approve a commit if a high-impact bug is visible. Fix it first when the user asked for implementation; report it when the user asked only for review.

Do not bury findings under a summary. Findings first, summary second.

If `summary-tables` is available, use it for residual risk, verification, and handoff summaries after findings.
