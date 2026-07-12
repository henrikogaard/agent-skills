---
name: delegated-subagents
description: Use only when the user explicitly requests delegated subagents, `$delegated-subagents`, or external OpenCode or Devin CLI workers for bounded repository work. Do not use for ordinary subagent delegation.
---

# Delegated Subagents

Keep the current Codex task as coordinator, reviewer, and sole user-facing
interface. Use external CLI agents as bounded workers, never as independent
owners of the user's request.

## Activation

This skill is opt-in. Invoke it only when the user explicitly says `delegated
subagents`, `$delegated-subagents`, or clearly requests external OpenCode or
Devin CLI workers.

Do not invoke it merely because a task involves coding, debugging, review,
triage, research, documentation, or parallel work. When this skill has not
been explicitly requested, use the default native GPT/Codex subagent management
when subagents are otherwise appropriate and authorized by the active task
instructions. Do not silently route work to external or cheaper models.

## Non-Interactive Rule

Do not send the user to a subagent for approvals, clarifications, status, or
follow-up. Launch every CLI with closed stdin and the runtime's automatic
permission profile.

- Let the main Codex task define scope and choose `read-only` or `edit`.
- Instruct subagents not to ask the user questions.
- Require a blocked subagent to record the decision it needs in its report.
- Let the main task answer routine subagent questions from repository context.
- Ask the user only from the main task when a genuine product, risk, credential,
  release, or scope decision cannot be resolved safely.
- Announce each launch with ID, task, tool/model, worktree/branch, limits, and
  expected output. External CLIs do not appear as native Codex subagent cards.

## Coordinator Ownership

Subagents may inspect, edit isolated worktrees, test, review, and produce
closure evidence. The main Codex task must inspect reports and diffs, rerun
appropriate verification, and explicitly accept, reject, or request follow-up.

Do not let subagents push, create PRs, close issues, move project items to
`Done`, merge, release, deploy, rotate credentials, or make final
security/privacy/release decisions. Only the main task may perform those actions,
and only when the user has authorized the specific external action.

## Workflow

1. Define the task and acceptance criteria.
2. Select a task type: `scout`, `bulk`, `code-small`, `debug`, `review`,
   `closure-validation`, `local`, or `long-autonomous`.
3. Read `references/model-matrix.md` and honor the user's model preference first.
4. Create a manifest from `references/task-manifest-template.json` for editing,
   issue, PR-readiness, or closure-validation work.
5. Create a prompt from `references/subagent-prompt-template.md`.
6. Launch through `scripts/spawn-opencode.sh` or `scripts/spawn-devin.sh`.
7. Monitor `scripts/status.sh`; report status immediately whenever the user asks.
8. Let the runtime kill and replace timed-out, silent, resource-heavy, dead, or
   provider-unavailable attempts within the bounded model chain.
9. Parse the structured report, inspect the managed worktree and logs, and
   accept, reject, or request another pass.
10. Use a separate review subagent after meaningful implementation, then use
    closure validation when acceptance evidence is still needed.
11. Run final verification in the main task.
12. Cancel/reap all active workers, preserve useful dirty worktrees, and prune
    expired logs.

Read `references/runtime-contract.md` before operating status, cancellation,
cleanup, resource overrides, or worktree lifecycle.

## Launch Examples

Read-only scout:

```bash
scripts/spawn-opencode.sh \
  --task scout \
  --prompt-file /absolute/path/prompt.txt \
  --workdir /absolute/path/repo \
  --permission-profile read-only
```

Bounded edit with manifest and automatic fallback:

```bash
scripts/spawn-opencode.sh \
  --task code-small \
  --prompt-file /absolute/path/prompt.txt \
  --manifest /absolute/path/manifest.json \
  --workdir /absolute/path/repo \
  --permission-profile edit
```

Longer Devin/SWE 1.7 task:

```bash
scripts/spawn-devin.sh \
  --task long-autonomous \
  --prompt-file /absolute/path/prompt.txt \
  --manifest /absolute/path/manifest.json \
  --workdir /absolute/path/repo \
  --models swe-1.7 \
  --permission-profile edit
```

The wrappers print the run directory immediately. Report that ID and selected
model to the user rather than hiding routing behind the resolver.

## Isolation And Scope

Default every run to a managed Git worktree under
`~/.codex/worktrees/delegated-subagents`. This protects the user's active checkout
while allowing non-interactive CLI permissions.

- Refuse managed execution from a non-Git directory or detached HEAD.
- Use `--isolation none` only for an explicitly safe throwaway directory.
- Reject a read-only run that changes files.
- For edit runs, include `allowed_paths` in the manifest and reject changes
  outside those paths.
- Preserve rejected or dirty worktrees for the main task to inspect.
- Remove a delegated worktree only when clean; never discard useful changes.

## Model And Cost Policy

Use already-paid capacity before scarce GPT/Codex coordination tokens:

1. OpenCode free models for scouts, bulk work, summaries, and light debugging.
2. aiRouter for broad free/unlimited delegated work.
3. Mistral Medium/Codestral for stronger coding, debugging, and review.
4. Devin/SWE 1.7 for longer bounded work.
5. OpenCodeGo only when the user permits limited subscription usage or the policy
   explicitly allows it.
6. Preserve the main GPT/Codex task for coordination and final judgment.

Refresh the live snapshot with `scripts/refresh-models.sh` and inspect measured
outcomes with `scripts/model-scorecard.sh`. Update
`references/model-matrix.md` when providers or model names drift.

## Fallback Rules

Fallback only for explicit provider/model unavailability, rate/quota exhaustion,
capacity errors, timeout, idle timeout, resource limit, or dead process.

Do not fallback for auth failures, permission failures, dirty/conflicted state,
ambiguous scope, broken code/tests, malformed reports, failed acceptance
criteria, poor patches, or policy violations. Return those to the main task.

Default to one external attempt and one active external worker. A failed,
cancelled, or unsuitable worker returns control to the main task; additional
external attempts require an explicit `--max-attempts` override. Record every
attempt and replacement. Never retry forever or retry the same model twice.

## Context And Cache Discipline

Treat provider prompt caching as opportunistic, not a correctness or cost
guarantee. Keep each worker's task narrow, use one pinned provider/model for a
batch when cache reuse matters, and keep stable instructions before the
task-specific tail.

- Inspect only files, paths, and commands named in the prompt or manifest.
- Do not read lockfiles, generated output, dependency trees, or full test logs
  unless they are directly needed for the acceptance criteria.
- Reuse a concise scout report or file/line inventory instead of making a new
  worker rediscover the whole repository.
- The OpenCode worker profile disables unrelated MCP tools by default. Enable
  them only through an explicit, task-specific configuration override.
- Keep the worker model input limit below the provider's fair-use threshold and
  retain automatic compaction/pruning. Verify the local limit before changing it.

## Status And Decisions

When the user asks for status, pause coordination and report active, completed,
failed, replaced, rejected, blocked, and cancelled workers with their models.

| ID | Task | Tool/model | State | Last activity | RSS | Main-task decision |
|---|---|---|---|---|---|---|
| `run-id` | issue triage | `opencode/model` | running | timestamp | 420 MB | pending |

Use these decisions:

- `accepted`: runtime policy passed and the main task independently verified the useful output.
- `rejected`: incorrect, unsafe, malformed, stale, off-scope, or failed criteria.
- `needs-follow-up`: partial/blocked result requiring another bounded pass.
- `replaced`: dead/unavailable attempt replaced with the next announced model.

Runtime `accepted` is only an input to main-task review; it is never automatic
approval for PR, merge, release, issue closure, or project completion.

## Delegation Shape

| Situation | Default delegation |
|---|---|
| Small issue or bug | One scout/debug worker; main task implements or reviews. |
| Medium issue | One implementation worker, then one independent review worker. |
| Large issue with independent areas | Two or three workers with non-overlapping manifests. |
| Many issues/branches/repos | Multiple bulk scouts, bounded by machine limits. |
| Ready-to-close issue | One closure-validation worker using the checklist. |
| Security/privacy/release work | Workers investigate; main task decides and edits conservatively. |

Do not let multiple edit workers touch the same files concurrently. Prefer
parallel investigation followed by serial implementation and review.

## Closure Validation

Read `references/closure-readiness-checklist.md`. Require the closure worker to
read the issue, linked PR/project state, relevant docs, current branch/worktree,
and explicit acceptance criteria. It must run focused checks and recommend one
of `ready-for-pr`, `ready-for-review`, `needs-fix`, `blocked`, or
`not-implemented` with exact evidence.

The main task resolves contradictions, checks the actual diff and commands, and
decides the next action. Do not mark `Done` or close review-stage issues without
explicit user QA/signoff when repository policy requires it.

## Process And Resource Safety

The shared runtime uses atomic JSON state, unique UUID-backed run directories,
global/per-repo concurrency limits, heartbeats, wall and idle timeouts, RSS
ceilings, process groups, TERM/KILL escalation, process reaping, and PID reuse
protection. It stores prompts/logs with owner-only permissions outside repos and
prunes terminal runs after 14 days by default.

Use:

```bash
scripts/status.sh
scripts/cancel-run.sh <run-id>
scripts/cleanup-run.sh --dry-run
scripts/cleanup-run.sh
python3 scripts/delegate.py prune --days 14
```

Never leave raw `opencode` or `devin` sessions running in the background.

## Bundled Files

- `scripts/delegate.py`: shared runner and command-center CLI.
- `scripts/runtime.py`: state, report, provider-failure, and process-identity primitives.
- `scripts/spawn-opencode.sh`: OpenCode model routing compatibility wrapper.
- `scripts/spawn-devin.sh`: explicit-model Devin compatibility wrapper.
- `scripts/status.sh`, `scripts/cancel-run.sh`, `scripts/cleanup-run.sh`: operations.
- `scripts/refresh-models.sh`, `scripts/model-scorecard.sh`: model maintenance.
- `scripts/preflight.sh`: CLI and runtime readiness check.
- `references/model-matrix.md`: current routing preferences.
- `references/subagent-prompt-template.md`: bounded worker prompt.
- `references/subagent-report-template.md`: validated report contract.
- `references/task-manifest-template.json`: machine-readable scope and criteria.
