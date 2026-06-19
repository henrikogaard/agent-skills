---
name: repo-memory
description: Use when entering an existing repository, learning recurring project conventions, updating durable AI-facing notes, or preserving commands, architecture, labels, branch rules, release steps, gotchas, and local workflow knowledge.
---

# Repo Memory

Capture durable project knowledge so future sessions do not rediscover the same commands, conventions, and traps.

## What To Read First

Look for existing instruction and memory files before creating anything new:

- `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.cursorrules`
- `.codex/`, `.claude/`, `.opencode/`
- `README.md`, `CONTRIBUTING.md`, `docs/`, runbooks, worklogs

Follow existing repo conventions for where durable notes belong.

## What To Preserve

- Setup commands, test commands, build commands, and dev server ports.
- Architecture boundaries, important modules, data flows, and ownership rules.
- Branch, commit, PR, issue label, project board, and release conventions.
- Known gotchas: generated files, flaky tests, platform-specific behavior, migration traps.
- Repeated manual QA paths and browser routes.
- Tooling quirks that caused real friction.

## Memory Rules

Keep memory short, factual, and actionable. Prefer bullets over narrative.

Do not store secrets, credentials, private tokens, or sensitive personal data.

Do not record one-off facts that will be stale next week unless they explain an active branch or plan.

When no obvious memory file exists, propose a location instead of scattering notes. Good defaults are `AGENTS.md` for agent instructions or `docs/worklog.md` for chronological breadcrumbs.

When updating memory, include only durable facts learned from evidence or explicit user preference.

## Where To Put It

| Memory type | Preferred location |
|---|---|
| Agent behavior, repo rules, required commands, collaboration norms | `AGENTS.md` |
| Setup, install, run, test, and troubleshooting commands | `README.md` or `CONTRIBUTING.md` |
| Architecture boundaries, diagrams, data flow, external dependencies | `ARCHITECTURE.md`, `docs/architecture.md`, or README architecture section |
| Chronological decisions, active branch notes, issue breadcrumbs | `docs/worklog.md` |
| Release, deploy, rollback, QA, and support steps | Runbook or release docs |

## Output Shape

```markdown
Repo memory update

| Fact | Evidence | Destination |
|---|---|---|
| `npm run test:unit` is the focused unit test command | `package.json` script | `AGENTS.md` |
| Auth refresh flow depends on local storage key X | Code inspection | `docs/worklog.md` |
```

If `summary-tables` is available, use it for memory proposals and updates.
