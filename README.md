# Agent Skills

Portable personal Agent Skills for Codex, OpenCode, Claude Code, and compatible harnesses. This repository is the editable source of truth; installed skill directories are deployments, not authoring locations.

## Skill Catalog

These are Henrik's custom personal workflow skills. Links point to each
skill's `SKILL.md`.

| Skill | Category | Use it for |
|---|---|---|
| [`agents-md-architect`](agents-md-architect/SKILL.md) | Instructions | Designing, auditing, and layering global, repo, nested, and tool-specific agent instruction files without duplicating rules. |
| [`architecture-diagrams`](architecture-diagrams/SKILL.md) | Documentation | Creating and maintaining Mermaid conceptual, logical, dependency, external-party, high-level, and low-level architecture diagrams. |
| [`change-surface-map`](change-surface-map/SKILL.md) | Planning | Mapping affected files, APIs, data contracts, tests, docs, build scripts, and hidden cross-module coupling before implementation. |
| [`completion-handoff`](completion-handoff/SKILL.md) | Handoff | Reporting shipped work, verification, commit/push/PR state, leftovers, risks, and exact next steps. |
| [`debugging-process`](debugging-process/SKILL.md) | Debugging | Reproducing, isolating, diagnosing, fixing, and verifying bugs, test failures, regressions, and broken builds. |
| [`delegated-subagents`](delegated-subagents/SKILL.md) | Delegation | Manual-only external-polish workflow using OpenCode, Devin, Cursor, or Mistral workers with a mandatory diff-hashed Codex final review. |
| [`design-system-guard`](design-system-guard/SKILL.md) | Frontend | Reviewing UI changes for tokens, component consistency, i18n, responsiveness, accessibility, and visual polish. |
| [`docs-sweep`](docs-sweep/SKILL.md) | Documentation | Deciding and updating the right README, worklog, changelog, ADR, runbook, QA, or security docs after repository changes. |
| [`github-project-hygiene`](github-project-hygiene/SKILL.md) | GitHub | Reconciling GitHub issues, labels, comments, project-board Status fields, QA state, stale notes, and closeout readiness. |
| [`implementation-process`](implementation-process/SKILL.md) | Implementation | Executing approved plans in small verified slices with checkpoints, tests, docs, and final review. |
| [`issue-to-plan`](issue-to-plan/SKILL.md) | Planning | Turning issues, bug reports, feature requests, product notes, or investigations into executable engineering plans. |
| [`lifecycle-router`](lifecycle-router/SKILL.md) | Lifecycle | Routing broad build/fix/plan/design/review requests into the right lifecycle phase without over-gating simple tasks. |
| [`migration-safety`](migration-safety/SKILL.md) | Data | Reviewing schema changes, migrations, backfills, data corrections, indexes, constraints, enum changes, and rollback plans. |
| [`needs-analysis`](needs-analysis/SKILL.md) | Lifecycle | Clarifying goals, users, constraints, risks, unknowns, and the smallest useful first slice before requirements or design. |
| [`pr-description`](pr-description/SKILL.md) | GitHub | Drafting reviewer-friendly PR bodies with context, changes, tests, risks, screenshots, and linked issues. |
| [`privacy-local-first-review`](privacy-local-first-review/SKILL.md) | Review | Reviewing telemetry, external calls, credentials, secrets, local-first behavior, data storage, auth, permissions, encryption, sync, and cloud dependencies. |
| [`release-surface-guard`](release-surface-guard/SKILL.md) | Release | Preventing accidental version, changelog, in-app release note, updater, tag, release branch, and deploy-surface drift. |
| [`repo-memory`](repo-memory/SKILL.md) | Memory | Capturing durable repo conventions, commands, architecture notes, branch rules, release steps, gotchas, and local workflow knowledge. |
| [`requirements-spec`](requirements-spec/SKILL.md) | Lifecycle | Converting clarified needs into scope, acceptance criteria, edge cases, non-functional requirements, and done definition. |
| [`review-before-commit`](review-before-commit/SKILL.md) | Review | Performing a final bug, regression, security, data-loss, behavior, missing-test, and unrelated-change review before publishing. |
| [`safe-git-handoff`](safe-git-handoff/SKILL.md) | Git | Protecting unrelated work and staging, committing, pushing, or handing off only intentional git changes. |
| [`skill-maintainer`](skill-maintainer/SKILL.md) | Skills | Auditing, documenting, validating, classifying, syncing, and installing personal skill folders and metadata. |
| [`solution-design`](solution-design/SKILL.md) | Lifecycle | Comparing approaches, selecting a design, and documenting architecture, dependencies, rollout, and verification before coding. |
| [`summary-router`](summary-router/SKILL.md) | Summary | Routing generic summary, status, comparison, reporting, and readout requests to `summary-tables` when appropriate. |
| [`summary-tables`](summary-tables/SKILL.md) | Summary | Formatting plan summaries, acceptance criteria, verification, gap reports, review suggestions, and close-outs as compact evidence-backed tables. |
| [`verification-matrix`](verification-matrix/SKILL.md) | Verification | Choosing and reporting targeted tests, builds, browser QA, migration checks, security checks, and manual verification. |

## Common Skill Chains

| Work type | Useful sequence |
|---|---|
| Full lifecycle | `lifecycle-router` -> `needs-analysis` -> `requirements-spec` -> `solution-design` -> `implementation-process` -> `verification-matrix` -> `review-before-commit` -> `completion-handoff` |
| New implementation | `lifecycle-router` -> `change-surface-map` -> `issue-to-plan` -> `implementation-process` -> `verification-matrix` -> `docs-sweep` -> `review-before-commit` -> `completion-handoff` |
| Bug or failing test | `debugging-process` -> `change-surface-map` -> `verification-matrix` -> `review-before-commit` -> `completion-handoff` |
| Design-first feature | `needs-analysis` -> `requirements-spec` -> `solution-design` -> `architecture-diagrams` -> `implementation-process` |
| GitHub issue cleanup | `github-project-hygiene` -> `summary-tables` -> `completion-handoff` |
| Commit or PR prep | `safe-git-handoff` -> `review-before-commit` -> `pr-description` -> `completion-handoff` |
| Docs architecture update | `architecture-diagrams` -> `docs-sweep` -> `summary-tables` |
| Release/version work | `release-surface-guard` -> `docs-sweep` -> `safe-git-handoff` |
| UI work | `design-system-guard` -> `verification-matrix` -> `docs-sweep` |
| Privacy/security-sensitive work | `privacy-local-first-review` -> `verification-matrix` -> `review-before-commit` |
| Skill repo maintenance | `skill-maintainer` -> `summary-tables` |

## Catalog Ownership

[`config/skills.yaml`](config/skills.yaml) declares every repository-managed skill and its install target:

- Portable skills target `~/.agents/skills` and stay in top-level repository folders.
- Future Codex-only skills target `~/.codex/skills` and live under `platforms/codex/`.
- Codex-managed system and plugin skills are external capabilities and are never copied or overwritten by this repository.
- The same active skill name must not be deployed to both portable and Codex roots.

The phase-one CLI is deliberately read-only. It validates, inventories, reports drift, and shows intended additions without changing installed files:

```bash
ruby scripts/skills validate
ruby scripts/skills inventory
ruby scripts/skills status
ruby scripts/skills plan
```

Use `--format json` for automation and `--agents-root` or `--codex-root` for temporary-home tests. `status` exits nonzero when expected skills are missing or drifted, or when a portable/Codex duplicate exists. `plan` reports locally modified installs as `blocked_drift` and never proposes deleting unmanaged folders.

## Install Portable Skills For Codex And OpenCode

The shared global deployment root is `~/.agents/skills`. OpenCode officially discovers this path, and Codex can consume the same portable skills without maintaining duplicate copies in `~/.codex/skills`.

Until the reviewed `sync` phase is implemented, inspect the plan and copy only the intended portable skill explicitly:

```bash
ruby scripts/skills plan
mkdir -p ~/.agents/skills
rsync -a summary-tables/ ~/.agents/skills/summary-tables/
```

For an OpenCode project-local install, use the portable project path:

```bash
mkdir -p .agents/skills
rsync -a /Users/henrik/Dev/Repos/agent-skills/summary-tables/ .agents/skills/summary-tables/
```

Restart the harness or start a new task if its skill inventory was loaded before the copy.

## Install A Skill In Claude Code

Install globally for all Claude Code projects:

```bash
mkdir -p ~/.claude/skills
rsync -a summary-tables/ ~/.claude/skills/summary-tables/
```

Install only for the current project:

```bash
mkdir -p .claude/skills
rsync -a /Users/henrik/Dev/Repos/agent-skills/summary-tables/ .claude/skills/summary-tables/
```

Claude Code can invoke skills automatically from their `description`, or directly with `/summary-tables`.

Claude Code documents `~/.claude/skills` rather than the portable global root. The future `agent-baseline` adapter will own that harness-specific deployment. Because OpenCode also discovers Claude-compatible paths, do not install the same skill into both `~/.agents/skills` and `~/.claude/skills` on an OpenCode host unless duplicate discovery has been explicitly resolved.

## Validate

Run the skill creator validator:

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py summary-tables
```

Validate every skill in this repo:

```bash
ruby scripts/skills validate
```

`ruby scripts/validate-skills.rb` remains as a compatibility entry point and uses the same manifest-aware validator. The repo-local tooling has no external gem dependencies. The official skill creator validator can still be run per skill, but it requires `PyYAML` in the Python environment running it.

## References

- [OpenAI: Plugins and skills in Codex](https://openai.com/academy/codex-plugins-and-skills/)
- [Claude Code: Extend Claude with skills](https://code.claude.com/docs/en/skills)
- [OpenCode: Agent Skills](https://opencode.ai/docs/skills/)

## License

This personal skill collection is licensed under the [MIT License](LICENSE.md).

## Repo Shape

Keep each skill folder lean:

```text
skill-name/
  SKILL.md
  agents/
    openai.yaml
  scripts/      # optional
  references/   # optional
  assets/       # optional
```

Put human-facing repository documentation here in the root README instead of adding per-skill README files.
