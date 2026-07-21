# Henrik's Agent Skills

Public source repository for reusable agent skills authored and maintained by
Henrik Øgård. The skills are portable workflow instructions for Codex,
OpenCode, Cursor, Devin, Claude Code, and other clients that support the open
Agent Skills layout.

This is deliberately a **custom-only repository**:

- Every published skill is Henrik-authored and declared in
  [`config/skills.yaml`](config/skills.yaml).
- Imported, copied, mirrored, provider-managed, and vendored third-party
  skills do not belong here.
- Codex system skills, Codex plugins, Expo's official plugin, CUA Driver, and
  other provider capabilities remain owned by their providers.
- Private reviewed vendor content belongs in the private `agent-baseline`
  repository, not this public repository.

## Skill catalog

The repository currently publishes 26 custom skills.

| Skill | Category | Use it for |
|---|---|---|
| [`agents-md-architect`](agents-md-architect/SKILL.md) | Instructions | Designing and auditing layered global, repository, nested, and tool-specific agent instructions. |
| [`architecture-diagrams`](architecture-diagrams/SKILL.md) | Documentation | Creating and maintaining Mermaid architecture and dependency diagrams. |
| [`change-surface-map`](change-surface-map/SKILL.md) | Planning | Mapping affected code, contracts, tests, docs, build surfaces, and hidden coupling. |
| [`completion-handoff`](completion-handoff/SKILL.md) | Handoff | Reporting changes, verification, publication state, leftovers, risks, and next steps. |
| [`debugging-process`](debugging-process/SKILL.md) | Debugging | Reproducing, isolating, fixing, and verifying bugs and regressions. |
| [`delegated-subagents`](delegated-subagents/SKILL.md) | Delegation | Running manual external-polish workers with mandatory diff-bound Codex review. |
| [`design-system-guard`](design-system-guard/SKILL.md) | Frontend | Reviewing tokens, component consistency, i18n, responsiveness, accessibility, and polish. |
| [`docs-sweep`](docs-sweep/SKILL.md) | Documentation | Updating the right README, worklog, changelog, ADR, runbook, QA, or security docs. |
| [`github-project-hygiene`](github-project-hygiene/SKILL.md) | GitHub | Reconciling issues, comments, labels, project status, QA state, and closeout evidence. |
| [`implementation-process`](implementation-process/SKILL.md) | Implementation | Executing approved work in small verified slices with tests and documentation. |
| [`issue-to-plan`](issue-to-plan/SKILL.md) | Planning | Turning an issue, bug, feature request, or investigation into an executable plan. |
| [`lifecycle-router`](lifecycle-router/SKILL.md) | Lifecycle | Selecting the appropriate lifecycle phase without over-gating simple work. |
| [`migration-safety`](migration-safety/SKILL.md) | Data | Reviewing migrations, backfills, constraints, indexes, data corrections, and rollback. |
| [`needs-analysis`](needs-analysis/SKILL.md) | Lifecycle | Clarifying users, goals, constraints, risks, unknowns, and the smallest useful slice. |
| [`pr-description`](pr-description/SKILL.md) | GitHub | Writing reviewer-friendly PR descriptions with context, verification, and risk. |
| [`privacy-local-first-review`](privacy-local-first-review/SKILL.md) | Review | Reviewing telemetry, credentials, local-first behavior, storage, auth, sync, and external calls. |
| [`release-surface-guard`](release-surface-guard/SKILL.md) | Release | Preventing accidental version, release-note, tag, updater, and deployment drift. |
| [`repo-memory`](repo-memory/SKILL.md) | Memory | Capturing durable repository conventions, commands, architecture, release steps, and gotchas. |
| [`requirements-spec`](requirements-spec/SKILL.md) | Lifecycle | Converting clarified needs into scope, acceptance criteria, edge cases, and done criteria. |
| [`review-before-commit`](review-before-commit/SKILL.md) | Review | Performing a final regression, security, data-loss, behavior, and test review. |
| [`safe-git-handoff`](safe-git-handoff/SKILL.md) | Git | Protecting unrelated work and publishing only the intended changes. |
| [`skill-maintainer`](skill-maintainer/SKILL.md) | Skills | Auditing, validating, documenting, syncing, and packaging custom skills. |
| [`solution-design`](solution-design/SKILL.md) | Lifecycle | Comparing approaches and documenting architecture, rollout, and verification. |
| [`summary-router`](summary-router/SKILL.md) | Summary | Routing status and comparison requests to an appropriate compact format. |
| [`summary-tables`](summary-tables/SKILL.md) | Summary | Producing evidence-backed plan, status, verification, gap, and closeout tables. |
| [`verification-matrix`](verification-matrix/SKILL.md) | Verification | Selecting and reporting focused tests, builds, browser QA, and manual checks. |

## Installation

### Henrik's managed devices

Use the private `agent-baseline` repository. It pins an immutable commit from
this repository, validates the public manifest, installs portable skills once
under `~/.agents/skills`, preserves unmanaged/provider skills, and records
rollback state.

Do not manually copy these skills into both `~/.agents/skills` and
`~/.codex/skills`; that creates duplicate active skills. Follow the
`agent-baseline` README's **New machine bootstrap** instructions instead.

### Standalone installation

Other users can install the custom collection without `agent-baseline`:

```bash
git clone https://github.com/henrikogaard/agent-skills.git
cd agent-skills
ruby scripts/skills validate
ruby scripts/skills inventory --agents-root "$HOME/.agents/skills"
ruby scripts/skills plan --agents-root "$HOME/.agents/skills"
```

After reviewing the plan, copy only declared top-level skill folders into the
portable Agent Skills location:

```bash
mkdir -p "$HOME/.agents/skills"
for skill in */; do
  [ -f "$skill/SKILL.md" ] || continue
  rsync -a --delete "$skill" "$HOME/.agents/skills/${skill%/}/"
done
```

Start a new agent session after installation so the harness refreshes skill
discovery. Provider-managed skills and plugins must be installed through their
official provider rather than copied from this repository.

## Repository contract

```text
skill-name/
  SKILL.md
  agents/
    openai.yaml
  scripts/      # optional, only when the skill needs executable support
  references/   # optional, supporting material used by the skill
  assets/       # optional, reusable non-code assets
```

The manifest is the source of truth:

- `ownership: first-party`
- `publication: public`
- portable skills target only `agents`
- genuinely Codex-specific custom skills live under `platforms/codex/`
- every folder name matches its `SKILL.md` frontmatter name
- every skill includes `agents/openai.yaml`

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full publication rules and
[SECURITY.md](SECURITY.md) for the public-safety boundary.

## Validation

Run both repository checks before publishing:

```bash
ruby scripts/skills validate --format json
ruby tests/test_skills_cli.rb
```

The validator checks the manifest, custom-only ownership boundary, skill
frontmatter, OpenAI metadata, filesystem coverage, routing, collisions, and
README links without external gems.

## Useful skill chains

| Work | Suggested sequence |
|---|---|
| Full lifecycle | `lifecycle-router` → `needs-analysis` → `requirements-spec` → `solution-design` → `implementation-process` → `verification-matrix` → `review-before-commit` → `completion-handoff` |
| Bug or regression | `debugging-process` → `change-surface-map` → `verification-matrix` → `review-before-commit` → `completion-handoff` |
| GitHub delivery | `github-project-hygiene` → `safe-git-handoff` → `pr-description` → `completion-handoff` |
| Skill maintenance | `skill-maintainer` → `summary-tables` |

## License

This custom skill collection is licensed under the [MIT License](LICENSE).
