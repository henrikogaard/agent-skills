---
name: agents-md-architect
description: Use when creating, auditing, refactoring, or layering global, repository, nested, or tool-specific agent instruction files such as AGENTS.md, CLAUDE.md, Codex globals, project rules, operating contracts, or handoff docs.
---

# Agents.md Architect

Design agent instructions so stable personal preferences live globally and project-specific rules stay local. The goal is a clean instruction stack that is easy for future agents to follow without duplicating or contradicting itself.

## When To Use

Use this skill for:

- Creating or revising global `AGENTS.md`.
- Auditing repo `AGENTS.md` / `CLAUDE.md` files.
- Deciding whether a rule belongs in global, repo root, nested folder, or a tool-specific compatibility file.
- Merging duplicate agent instructions across tools.
- Turning repeated working preferences into durable instructions.

Do not use this for ordinary code changes unless agent instructions are part of the change.

## Layering Model

Sort each rule into the narrowest durable layer:

| Layer | Belongs there |
|---|---|
| Global | Personal style, safety defaults, communication preferences, commit caution, summary format |
| Repo root | Project source of truth, issue workflow, commands, docs, ADRs, architecture, release rules |
| Nested folder | Subsystem-only conventions, generated code warnings, package-specific commands |
| Tool compatibility | Pointers from `CLAUDE.md`, `GEMINI.md`, or similar back to canonical `AGENTS.md` |

If a rule mentions a project name, board ID, command, tech stack, domain, deploy target, or path inside a repo, it usually does not belong globally.

## Audit Flow

1. Find instruction files: `AGENTS.md`, `AGENTS.override.md`, `CLAUDE.md`, tool-specific files, and nested copies.
2. Read the current global instructions if accessible.
3. Build a table of rules: rule, current file, recommended layer, reason.
4. Identify conflicts, stale project details, and duplicate wording.
5. Draft concise replacements or patches.
6. Preserve explicit project constraints even if they conflict with global defaults.

## Output Shape

Use a compact table:

```markdown
| Rule | Current location | Recommended location | Reason |
|---|---|---|---|
| Do not commit without asking | Several repo files | Global | Personal default repeated across repos |
| Project 4 status IDs | Global draft | Repo only | Project-specific GitHub machinery |
```

Then provide the proposed file text or patch summary.

## Rules

- Keep global instructions short enough to read every session.
- Do not move repo-specific safety rules upward just because they repeat in two repos.
- Prefer canonical `AGENTS.md` plus compatibility pointers over maintaining divergent copies.
- When changing instructions, include why each moved rule belongs at that layer.
- If `summary-tables` is available, use it for audits and final recommendations.
