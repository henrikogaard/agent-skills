# Runtime Contract

Use `scripts/delegate.py` through the shell wrappers. Runtime state lives under
`~/.codex/state/delegated-subagents`, outside repositories, with owner-only
permissions.

## State

Each run has an atomic `state.json`, copied prompt, attempt logs, and optional
manifest. Important states are:

| State | Meaning |
|---|---|
| `starting` | Admitted under concurrency limits, not launched yet. |
| `running` | Process identity, heartbeat, model, and RSS are current. |
| `accepted` | Structured report is valid and policy checks passed. Main Codex review is still required. |
| `needs-follow-up` | Agent reported partial, blocked, or unknown acceptance evidence. |
| `rejected` | Invalid report, failed criterion, model mismatch, or scope violation. |
| `provider-unavailable` | Attempt may fall back to the next model. |
| `timeout`, `idle-timeout`, `resource-limit` | Process group was terminated and may be replaced. |
| `cancelled` | Main Codex task cancelled and reaped the process group. |
| `orphaned` | Metadata exists but process identity cannot be proven; cleanup refuses to kill it. |

An exit code of zero is not acceptance. The runtime validates `STATUS`, `MODEL`,
`TASK_TYPE`, `REPO`, acceptance-criteria entries, and closure recommendation.

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Runtime accepted the structured report; main Codex review remains. |
| `3` | Needs follow-up. |
| `4` | Rejected report or policy violation. |
| `75` | Concurrency admission denied. |
| `124` | Attempts exhausted after timeout, idle, resource, or provider failures. |
| `130` | Cancelled. |

## Permissions And Isolation

- Run all CLIs non-interactively with closed stdin.
- Use OpenCode `--pure --auto`; protect the repository with a managed worktree.
- Use Devin `auto` for read-only and `accept-edits` for edit jobs, always with
  `--sandbox` and workspace trust enabled.
- Default to managed worktrees for both read-only and edit jobs.
- Reject read-only jobs that change files.
- When a manifest has `allowed_paths`, reject edit jobs that touch other paths.
- Preserve dirty delegated worktrees for main-thread inspection. Never delete
  them automatically.

The main Codex task chooses the permission profile. Subagents never ask the user
for approvals. A subagent that needs a decision reports `blocked` or
`needs-follow-up`; the main task resolves it or asks the user itself when a real
project-level decision is required.

## Resource And Process Safety

Defaults are three concurrent runs globally, two per repository, 4 GiB RSS for
OpenCode, 6 GiB for Devin, nice level 5, and three attempts. Override with the
documented `SUBAGENT_*` environment variables or wrapper flags.

The runner stores PID, PGID, process start signature, and command fingerprint.
Cleanup kills a process group only when PID, PGID, and start signature still
match. It sends TERM, waits, sends KILL if needed, and reaps owned children.

## Operations

```bash
scripts/status.sh
scripts/status.sh --json
python3 scripts/delegate.py watch
scripts/cancel-run.sh <run-id-or-directory>
scripts/cleanup-run.sh --dry-run
scripts/cleanup-run.sh
scripts/refresh-models.sh --json
scripts/model-scorecard.sh --json
python3 scripts/delegate.py prune --days 14
```

Run `prune` after completed work to remove old prompts and logs. The default
retention is 14 days. It never removes active runs.
