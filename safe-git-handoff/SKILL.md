---
name: safe-git-handoff
description: Use when preparing to commit, stage, push, hand off, inspect git status, protect unrelated work, avoid destructive commands, or summarize local changes in a shared or multi-agent workspace.
---

# Safe Git Handoff

Protect the user's workspace and other agents' work while preparing clean commits or handoffs. Stage only intentional changes and make repository state explicit.

## When To Use

Use this skill:

- Before committing, pushing, opening a PR, or handing back local work.
- When unexpected modified or untracked files appear.
- In worktrees or repos where multiple agents may be active.
- When the user asks what changed, what is staged, or what is safe to commit.
- Before running risky git operations.

## Safety Defaults

- Do not commit, push, tag, release, deploy, rewrite history, or close issues unless Henrik explicitly asks.
- Do not run destructive commands such as `git reset --hard`, `git checkout -- <path>`, `git clean`, rebase, stash pop/apply, or history rewriting without explicit instruction.
- Avoid `git add .` and `git add -A`; stage explicit paths that belong to the agreed deliverable.
- Treat unexpected changes as belonging to Henrik or another agent.
- Never revert user changes unless explicitly requested.

## Handoff Flow

1. Run `git status --short` and identify changed, staged, untracked, and ignored-relevant files.
2. Inspect `git diff --stat`, `git diff`, and `git diff --cached` as needed.
3. Separate changes into: mine, user/other-agent, generated/ignored, uncertain.
4. Stage explicit paths only when committing was requested.
5. If committing, use a clear message that describes actual effect.
6. Report commit SHA, branch, push target, PR, and remaining local changes.

## Unexpected Changes

If a file you did not intentionally edit appears:

- Do not stage or revert it.
- Mention it in the handoff as unrelated or uncertain.
- If it blocks the task, pause and ask how to proceed.

## Output Shape

```markdown
| Path | State | Include? | Reason |
|---|---|---|---|
| `src/auth.ts` | modified | Yes | Implements requested fix |
| `notes.md` | untracked | No | Unrelated local note |
```

Then include:

- `Committed:` short SHA or `Not committed`
- `Pushed:` remote/branch or `Not pushed`
- `Left out:` explicit unrelated files
- `Next:` one concrete recommendation

## Rules

- Use `review-before-commit` when a bug/regression review is needed before publishing.
- Use `completion-handoff` for the final user-facing handoff after commit/push/PR state is known.
- If `summary-tables` is available, use it for the change-state table.
