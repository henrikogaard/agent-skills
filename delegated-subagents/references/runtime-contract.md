# Runtime Contract

Runtime state lives under `~/.codex/state/delegated-subagents/runs` with
owner-only permissions. Use the shell wrappers for launches and
`scripts/delegate.py` for review/state operations.

## State And Acceptance

| State | Meaning |
|---|---|
| `starting`, `running` | Worker admitted or active. |
| `worker-complete` | Worker report and scope policy passed; no review or acceptance implied. |
| `pre-review-complete` | A linked independent external review completed. |
| `codex-review-required` | Final diff-hashed packet exists; Codex review is mandatory. |
| `changes-required` | Codex found issues; at most one automatic external repair is allowed. |
| `blocked` | A user, credential, scope, product, or risk decision is required. |
| `approved` | Codex reviewed the complete final diff and recorded verification. |
| `needs-follow-up` | Worker reported partial or unknown evidence. |
| `rejected` | Report, scope, verification, or policy failed. |
| `timeout`, `idle-timeout`, `resource-limit`, `cancelled` | Worker was terminated safely. |
| `orphaned` | Process identity cannot be proven; cleanup refuses to kill it. |
| `accepted` | Legacy history only; new workers never enter this state. |

An exit code of zero from a worker means `worker-complete`, not approval. Only
`record-review --reviewer codex --decision approved` may create `approved`.

## External Polish And Final Review

Run an independent reviewer against the implementation worktree with
`--isolation none --permission-profile read-only`. Then create the packet:

```bash
python3 scripts/delegate.py review-packet <implementation-run> \
  --pre-review-run <review-run>
```

The packet contains run metadata, changed paths, acceptance evidence, residual
risk, the complete tracked and untracked final diff, and its SHA-256 hash. It
does not copy worker transcripts, prompts, environment dumps, or complete test
logs into the parent context.

After reading every changed line and checking verification, Codex records:

```bash
python3 scripts/delegate.py record-review <implementation-run> \
  --reviewer codex \
  --decision approved \
  --verification-summary "full diff reviewed; focused checks passed" \
  --residual-risk "none"
```

Valid decisions are `approved`, `changes-required`, and `blocked`. A changed
diff hash makes an existing approval stale. `status` detects this and returns
the run to `codex-review-required`.

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Operation succeeded; for a worker this means `worker-complete`. |
| `3` | Worker needs follow-up. |
| `4` | Worker report or policy rejected. |
| `75` | Concurrency admission denied. |
| `124` | Attempts exhausted after availability/resource failure. |
| `130` | Cancelled. |

## Permissions And Isolation

- OpenCode uses `--pure --auto` in a managed worktree.
- Devin maps read-only/edit to `auto`/`accept-edits` with its sandbox enabled.
- Cursor uses headless print mode, workspace trust, sandboxing, plan mode for
  read-only, and force approval only inside an edit-scoped managed worktree.
- Cursor receives a dedicated read-only `input/` root for its prompt, never the
  run directory containing `state.json` or review records.
- Closed stdin is mandatory for all workers.
- Read-only runs that change files are rejected.
- Edit runs with a manifest are rejected for changes outside `allowed_paths`.
- Dirty delegated worktrees are preserved for inspection.

## Limits And Fallback

Current defaults are one active run globally, one per repository, and one model
attempt. Provider availability failures may use an explicitly enabled fallback.
Bad code, failed tests, malformed reports, auth/permission failures, ambiguous
scope, and policy violations return to Codex without automatic model churn.

Default external polish is one implementer, one independent reviewer, and one
repair cycle. A second `changes-required` decision returns control to Codex.

## Live Models

```bash
scripts/refresh-models.sh --task code-small --json
scripts/model-scorecard.sh --json
```

Every refresh calls `opencode models`. The snapshot records all visible models
and classifies every current `opencode/*free*` route as `usable`, `probe-only`,
or `excluded` for the requested task. Unknown free models require a bounded
probe; three recent comparable hard failures exclude a route until reprobed.

Devin routing uses `swe-1.7` as a stable family. An exact safe user request has
priority, followed by `DEVIN_SWE_MODEL`, the most recently successful observed
family variant, and finally the compatibility alias. State and reports retain
the exact raw model plus the stable family and variant; provider names such as
`SWE-1.7 Max Beta` and `SWE-1.7 Lightning Beta` do not require matrix changes.

## Operations

```bash
scripts/status.sh --json
scripts/usage-report.sh --json
scripts/usage-report.sh --run <run-id> --json
scripts/usage-report.sh --codex-session /abs/path/to/codex-rollout.jsonl --json
scripts/dashboard-export.sh --output /abs/path/to/delegated-usage.json
scripts/dashboard-export.sh --privacy private --output /abs/path/to/private-usage.json
scripts/cancel-run.sh <run-id>
scripts/cleanup-run.sh --dry-run
scripts/cleanup-run.sh
python3 scripts/delegate.py prune --days 14
```

The runtime stores atomic JSON, UUID-backed directories, process identities,
heartbeats, time/RSS limits, and process groups. Cancellation verifies PID,
PGID, and start signature before TERM/KILL. Pruning removes only terminal runs
older than the requested retention window.

## Usage Telemetry

New attempts store a normalized `usage` object in `state.json` and model
history. Devin totals come from `devin-export.json`; OpenCode and Cursor use
their structured output. Missing provider counters are `null` with
`source: unavailable`, never inferred from response length.

`usage-report` separates input, cache read/write, output, reasoning, total
tokens, reported nominal cost, billing class, and known actual charge. Free
routes have an actual charge of zero. Subscription routes keep actual charge
unknown unless independently known; reported model cost is not treated as a
subscription bill.

With `--codex-session`, the report reads only `token_count` events from the
specified rollout JSONL and subtracts cumulative snapshots surrounding the
selected run window. The resulting delegated share is available only when both
external and Codex totals are measured. Raw prompts and transcripts are never
included in the report or review packet.

For historical runs without a normalized `usage` object, the reporter reads an
existing Devin export and attempt log without mutating old state. Historical
OpenCode or Cursor attempts without structured counters remain unavailable and
are reflected in capture coverage.

`dashboard-export` defaults to public schema version 2. It emits only calendar
months, strict provider names, and coarse attempt, coverage, and token bands.
Provider/month rows require at least 10 attempts; smaller samples are
suppressed. It excludes attempts, exact models and variants, task/result
labels, billing, costs, exact token counts, exact timestamps, prompts,
transcripts, repository/worktree paths, branches, run/session identifiers,
commands, environment values, credentials, and raw errors.

`--privacy private` explicitly writes the detailed schema version 1 operational
snapshot. That mode retains allowlisted attempt and billing facts and is for
local/private use only; never commit it to a public repository.
