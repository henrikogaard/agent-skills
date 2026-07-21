---
name: change-surface-map
description: Use before implementing, refactoring, reviewing, or planning changes that may touch multiple files, APIs, UI routes, data models, migrations, tests, docs, build scripts, or hidden cross-module contracts.
---

# Change Surface Map

Map the blast radius before editing. The goal is to avoid narrow fixes that miss callers, tests, docs, or data contracts.

## Workflow

Inspect the request, then search the repo for names, routes, feature flags, DTOs, commands, schemas, tests, docs, and prior worklog notes related to the change.

Build a concise map:

```markdown
| Surface | Evidence | Risk | Needed follow-up |
|---|---|---|---|
| API contract | `FrontendSessionDto`, `session.ts` | Clients may miss new field | Update TS type and bootstrap test |
| Persistence | migration + service | Backfill/default behavior | Add migration test |
| UI route | `/admin/settings` | Hidden state copy | Browser QA |
```

## Surfaces To Check

- Backend handlers, services, queues, jobs, permissions, and native commands.
- Frontend routes, state stores, generated clients, components, copy, and loading/error states.
- Data contracts, migrations, seeds, fixtures, serialization, import/export, and backwards compatibility.
- Tests at the right layer: unit, integration, e2e, browser/manual QA, migration tests.
- Docs, ADRs, runbooks, worklog breadcrumbs, issue/PR comments, and release notes.
- Operational effects: logs, metrics, rate limits, retries, feature flags, and rollout/rollback.

## Rules

Do not treat the map as permission to refactor everything. Mark unrelated cleanup as out of scope.

If a surface is suspected but not confirmed, label it "uncertain" and say what search or inspection would confirm it.

If `issue-to-plan` or `verification-matrix` is available, use them after the map when the user needs a plan or test strategy.

