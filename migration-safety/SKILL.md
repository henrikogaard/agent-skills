---
name: migration-safety
description: Use when creating, reviewing, planning, or validating database migrations, schema changes, backfills, data corrections, indexes, constraints, enum changes, or rollout/rollback plans that may affect persisted data.
---

# Migration Safety

Treat schema and data changes as rollout problems, not just code generation.

## Safety Matrix

Use this shape for planning or review:

```markdown
| Concern | Status | Evidence / action |
|---|---|---|
| Backwards compatibility | Needs check | old app version must tolerate nullable `expiresAt` |
| Data loss | Clear | additive column only |
| Rollback | Risk | down migration drops computed values |
| Verification | Planned | migration dry run + focused repository tests |
```

## Checklist

- Identify the database engine, migration framework, and deployment order.
- Prefer expand-contract for live systems: add nullable/defaulted fields, deploy code, backfill, then enforce constraints.
- Check old-code/new-schema and new-code/old-schema compatibility when deploys can overlap.
- Flag destructive operations: drop, rename, type narrowing, non-null without backfill, enum removal, cascade delete.
- Consider table size, locks, index creation mode, transaction boundaries, timeout risk, and batching.
- Define backfill behavior, idempotency, retry safety, and partial-failure handling.
- Verify generated model snapshots, pending-model checks, migration tests, and representative data paths.

## Rules

Never call a migration safe just because it compiles.

If rollback would lose data, say so plainly and describe the operational fallback.

If production deployment constraints are unknown, mark them unknown instead of assuming zero-downtime is unnecessary.

If `verification-matrix` is available, use it to plan the migration checks.

