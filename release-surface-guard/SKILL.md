---
name: release-surface-guard
description: Use when checking or changing versions, changelogs, release notes, in-app changelogs, updater manifests, package manifests, deploy/runbook steps, tags, release branches, or user-visible release surfaces.
---

# Release Surface Guard

Prevent accidental release churn. Version bumps, changelog entries, updater metadata, tags, and deploy notes should happen only when the repo's release rules and the user's request call for them.

## When To Use

Use this skill for:

- Version bump requests.
- Release or deploy procedures.
- Changelog and in-app changelog updates.
- Package/app/updater manifest changes.
- Deciding whether normal implementation should touch release surfaces.
- Preparing release handoff or release PRs.

## Release Surfaces

Check repo instructions first, then look for:

| Surface | Examples |
|---|---|
| Product version | `version.md`, `package.json`, app manifests, native build numbers |
| Changelog | `CHANGELOG.md`, `[Unreleased]`, release headings |
| In-app notes | status bars, admin changelogs, companion-app changelog arrays |
| Updater metadata | Tauri updater manifests, static update feeds |
| Deployment docs | `DEPLOY.md`, runbooks, environment docs |
| GitHub release state | tags, release branches, PR titles, issue closeouts |

## Decision Rules

- Do not bump versions unless the user explicitly asks or the repo says the current workflow requires it.
- Do not write derived dev/rc build identities back into product version files unless the repo specifically allows it.
- Keep internal changelog and user-facing in-app notes separate.
- In-app changelog entries should describe visible product value, not implementation mechanics.
- If a change is docs-only, internal-only, test-only, or invisible refactor, avoid user-facing release notes unless the repo says otherwise.
- Update all required version surfaces together when a real release/version change is requested.

## Flow

1. Read repo release/version/changelog rules.
2. Determine whether this task is normal implementation, checkpoint, release candidate, public release, or deploy.
3. List every release surface that may need updating.
4. Decide: update now, leave untouched, or ask Henrik.
5. Run repo-specific version/changelog checks when available.
6. Report touched and intentionally untouched surfaces.

## Output Shape

```markdown
| Surface | Action | Reason |
|---|---|---|
| `CHANGELOG.md` | Update `[Unreleased]` | User-requested change is notable |
| `version.md` | Leave untouched | No explicit release/version request |
| In-app changelog | Skip | Internal reliability fix, no visible user value |
```

End with `Net:` stating whether release surfaces are consistent.
