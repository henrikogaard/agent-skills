---
name: verification-matrix
description: Use when choosing, planning, running, or reporting tests and QA for a change, especially when different code surfaces require targeted unit, integration, migration, browser, manual, security, or build verification.
---

# Verification Matrix

Match verification to the real change surface. Prefer targeted, high-signal checks first, then broaden when shared contracts or user workflows changed.

## Matrix

Create a table before or after running checks:

```markdown
| Risk / behavior | Check | Command or target | Status |
|---|---|---|---|
| Token expiry default | Integration test | `dotnet test --filter TokenExpiry` | Passed |
| Admin UI display | Browser QA | `/admin/tokens` | Not run: needs dev server |
| Migration safety | Migration dry run | `dotnet ef migrations has-pending-model-changes` | Passed |
```

## Choose Checks

- Pure function or parser change: focused unit tests plus edge cases.
- Service/API contract change: integration tests, generated client/type checks, permission checks.
- UI change: source tests plus browser QA for primary route, empty/loading/error states.
- Data or migration change: migration validation, rollback/backfill/default behavior, compatibility with old code.
- Native/desktop/file-system change: platform-specific tests and manual smoke path when automation cannot cover it.
- Security-sensitive change: abuse cases, boundary checks, denial paths, audit/log behavior.
- Shared utility or cross-cutting refactor: broader suite and build/typecheck.
- Bug fix or regression: reproduce the original failure first, then add or run a regression check that would fail without the fix.

## Reporting Rules

Report exact commands and outcomes. "Tests pass" is weaker than "`npm test -- token`: 33 passed".

Include checks intentionally not run and the reason.

Do not substitute a broad green build for missing targeted verification when the risk is specific.

If `change-surface-map` is available, use it to decide what must be verified.

If the cause is still unknown, use `debugging-process` before treating verification as complete.
