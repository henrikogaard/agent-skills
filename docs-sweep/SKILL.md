---
name: docs-sweep
description: Use when deciding, checking, or updating documentation after code, workflow, architecture, release, setup, security, issue, UI, API, migration, or user-facing behavior changes in a repository.
---

# Docs Sweep

Treat documentation as part of the change when behavior, structure, operations, or user-facing surfaces change. The goal is to update the right durable docs without noisy documentation churn.

## When To Use

Use this skill:

- Before handoff for non-trivial implementation.
- When a repo requires worklog, changelog, README, ADR, deployment, security, or QA docs.
- When deciding whether a change needs docs.
- When preparing a commit that must include documentation.
- When code changed but docs may have drifted.

## Sweep Matrix

Check the repo instructions first, then use this default matrix:

| Change | Common docs to check |
|---|---|
| Setup, commands, repo layout | `README.md`, onboarding docs |
| Deployment, env, secrets, infra | `DEPLOY.md`, runbooks, ops docs |
| User-facing behavior | `CHANGELOG.md`, user manual, in-app changelog if repo allows |
| Architecture or long-lived pattern | ADRs, architecture docs, `AGENTS.md` if workflow changed |
| Security, auth, permissions, data isolation | `SECURITY.md`, permission matrix, audit docs |
| Database migrations or data lifecycle | migration docs, rollback notes, compliance docs |
| Non-trivial work session | worklog / engineering log |
| QA or manual testing | `docs/qa/*`, issue comment, smoke checklist |

## Decision Rules

- Update docs in the same patch when behavior, structure, workflow, setup, or operations changed.
- Do not add changelog or release notes for work that is not shipping or not being committed.
- Keep in-app changelogs user-facing and benefit-first; do not mirror internal refactors.
- If docs are not needed, state why in the handoff.
- Prefer updating existing canonical docs over creating new scattered notes.

## Sweep Flow

1. Read repo `AGENTS.md` documentation rules.
2. List changed surfaces from the diff or task.
3. Map each surface to required docs.
4. Update only affected docs.
5. Re-read changed docs for stale claims, wrong commands, and overbroad release wording.
6. Include documentation status in the final handoff.

## Output Shape

```markdown
| Doc surface | Needed? | Action |
|---|---|---|
| `README.md` | No | No setup or workflow change |
| `docs/worklog.md` | Yes | Added concise session entry |
| `CHANGELOG.md` | Yes | Added `[Unreleased]` entry for web-visible fix |
```

End with `Net:` explaining whether docs are complete or what remains.
