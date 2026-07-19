---
name: delegated-subagents
description: Use only when the user manually invokes delegated subagents or $delegated-subagents, or explicitly requests an external CLI worker or named external model. Never invoke automatically for ordinary delegation.
---

# Delegated Subagents

This is a **manual-only** skill. Keep Codex as the sole user-facing coordinator
and mandatory final reviewer while external CLI workers implement, investigate,
test, and polish bounded work.

## Manual-only Activation

Invoke only when the user explicitly says `delegated subagents`,
`$delegated-subagents`, requests an external OpenCode, Devin, Cursor, or Mistral
worker, or names an external worker model. `launch subagents with SWE 1.7` is an
explicit opt-in and routes through `scripts/spawn-devin.sh`.

Never self-trigger for generic coding, debugging, research, review, parallel
work, or a generic request for subagents. Those use Native Codex GPT subagent
management when otherwise authorized. Do not silently route work externally.
Keep `agents/openai.yaml` set to `allow_implicit_invocation: false`.

## Non-negotiable Review Gate

A successful worker stops at `worker-complete`; it is not accepted. External
reviewers may report findings and the implementer may repair them, but neither
may approve the work. Before recommending acceptance, Codex must:

1. Generate the final review packet with `scripts/delegate.py review-packet`.
2. Read the complete final diff and acceptance evidence.
3. Run or check proportionate final verification.
4. Record `approved`, `changes-required`, or `blocked` with
   `scripts/delegate.py record-review --reviewer codex`.

Approval is bound to the final diff hash. Any later change invalidates it and
returns the run to `codex-review-required`.

## Complexity Gate

Codex owns ambiguous product decisions, architecture, integration, security,
privacy, migrations, billing, release, deployment, and broad cross-cutting
work. External workers may handle bounded slices only when the goal, allowed
paths, acceptance criteria, and verification are explicit.

| Work shape | Owner |
|---|---|
| Ambiguous, cross-cutting, or high-risk decision | Main Codex task |
| Independent reasoning-heavy slice unsuitable for external tools | Native Codex GPT subagent |
| Bounded implementation or debugging | External implementer, external polish, full Codex review |
| Inventory, search, docs sweep, evidence collection | Free external scout when usable |

## Weighted External Model Matrix

Check the live inventory before every routing decision. Run
`scripts/refresh-models.sh --task <task> --json`; the runtime calls
`opencode models`, discovers every current `opencode/*free*` identifier, and
classifies it as `usable`, `probe-only`, or `excluded` using task fit and local
outcomes. Never rely only on a static free-model list. Unknown free models may
run a bounded scout/review probe but do not become default edit workers until a
smoke run succeeds.

| Task type | Primary | External polish/review | Fallback | Cost |
|---|---|---|---|---|
| `scout`, inventory, docs sweep | Best live usable `opencode/*free*` | Another free model only if evidence conflicts | `airouter/Qwen3.6` | Free |
| Simple docs or mechanical edit | Devin/SWE-1.7 family | Best live usable free reviewer | `composer-2.5-fast` | Free first |
| Bounded bug fix or small feature | Devin/SWE-1.7 family after smoke success | `composer-2.5-fast` or independent usable free reviewer | `composer-2.5` | Free first |
| Bounded debugging with unclear cause | `composer-2.5` | SWE 1.7 or Mistral Medium | Mistral Medium | Subscription |
| Approved complex multi-file slice | `composer-2.5` | SWE 1.7 or Mistral Medium from another family | Return to Codex | Subscription |
| Independent pre-review | Different family: usable free model, SWE 1.7, or Composer Fast | Not applicable | Mistral Medium | Cheapest fit |
| Closure evidence | Best live usable free review/general model | Deterministic checklist | `airouter/Qwen3.6` | Free |
| Large decomposable epic | Composer 2.5 coordinates bounded SWE/free workers | Independent reviewer per slice | Mistral only when requested | Subscription |
| Security/privacy/auth/migration/release | Strong external model may investigate or implement a narrow slice | Independent strong review | No automatic fallback | Codex owns decisions |

Cost facts for this installation:

- Devin's SWE-1.7 family, `airouter/*`, and live `opencode/*free*` routes are free.
- Cursor `composer-2.5` and `composer-2.5-fast` use the Cursor subscription.
- Mistral routes use the Mistral subscription.
- Main/native Codex uses scarce OpenAI subscription capacity; reserve it for
  scoping, full final review, integration, and decisions.

An explicit named model overrides the matrix when safe. Announce and record the
override. Do not use paid OpenCodeGo routes without explicit permission. Local
`omlx/*` models remain disabled.

## External Polish First

For meaningful edit work:

1. Codex creates one compact manifest and prompt.
2. Launch one implementer in a managed worktree.
3. Wait for completion; do not repeatedly poll or ingest full logs.
4. Run deterministic scope and verification checks.
5. Launch one independent external `review` worker against the same worktree
   with `--isolation none --permission-profile read-only`.
6. Give objective findings back to the implementer for at most one repair cycle.
7. Generate one compact, diff-hashed review packet linked to the pre-review run.
8. Codex performs the complete final review once and records the decision.

Use deterministic scripts, not models, for state transitions, changed-path
lists, diff hashes, manifests, and packet assembly. Do not send worker
transcripts, passing test logs, dependency trees, or repeated repository
context into the Codex task. Request only narrow failure excerpts when needed.

## Launchers

```bash
# Free implementation
# Set DEVIN_SWE_MODEL to the current exact provider name, for example
# "SWE-1.7 Max Beta". The family alias falls back to recent successful history.
scripts/spawn-devin.sh --task code-small --model swe-1.7 \
  --prompt-file /abs/prompt.txt --manifest /abs/manifest.json \
  --workdir /abs/repo --permission-profile edit

# Cursor implementation or repair
scripts/spawn-cursor.sh --task code-small --model composer-2.5 \
  --prompt-file /abs/prompt.txt --manifest /abs/manifest.json \
  --workdir /abs/repo --permission-profile edit

# Live-routed free scout/reviewer
scripts/spawn-opencode.sh --task review --policy only-free \
  --prompt-file /abs/review.txt --workdir /abs/delegated-worktree \
  --isolation none --permission-profile read-only
```

Every worker runs non-interactively with closed stdin. Require it to read the
applicable `AGENTS.md`, use `rtk` when available, remain inside manifest paths,
avoid external actions, and return the structured report. Workers never push,
create or merge PRs, close issues, deploy, release, rotate credentials, or ask
the user questions.

## Final Review Commands

```bash
python3 scripts/delegate.py review-packet <implementation-run> \
  --pre-review-run <review-run>

python3 scripts/delegate.py record-review <implementation-run> \
  --reviewer codex --decision approved \
  --verification-summary "full diff reviewed; focused checks passed" \
  --residual-risk "none"
```

Use `changes-required` or `blocked` instead of `approved` when appropriate.
Only an `approved` state permits recommending acceptance.

## Usage Measurement

Every new attempt records provider-reported input, cached input, output,
reasoning, total tokens, reported cost, and billing class when the worker CLI
exposes them. Missing counters stay `unavailable`; never estimate them from log
length. Free routes record zero actual charge even when a tool reports nominal
API-equivalent cost.

```bash
# External worker usage captured by this skill
scripts/usage-report.sh

# One run, machine-readable
scripts/usage-report.sh --run <run-id> --json

# Compare selected runs with the supervising Codex session window
scripts/usage-report.sh --codex-session /abs/path/to/codex-rollout.jsonl --json

# Write the allowlisted static snapshot used by the private dashboard
scripts/dashboard-export.sh --output /abs/path/to/delegated-usage.json
```

The optional Codex comparison uses cumulative token snapshots surrounding the
delegated run window. Treat its `delegated_share` as a workflow measurement:
the Codex delta includes all coordination and review activity in that session
window. The reporter reads existing Devin exports without modifying old state;
other old runs without structured usage remain unavailable and reduce capture
coverage. The dashboard exporter never invokes a model and publishes only
allowlisted aggregate and attempt facts; prompts, transcripts, repository
paths, session identifiers, command lines, and raw errors are excluded.

## Safety And Operations

Default to one active worker, one model attempt, one independent pre-review,
and one repair cycle. Fallback only for provider unavailability, quota/capacity,
timeout, resource limit, or a dead process. Never fallback for bad code, failed
tests, malformed reports, ambiguous scope, or policy violations.

Use managed Git worktrees by default. Preserve dirty or rejected worktrees.
Never delete useful changes. Read `references/runtime-contract.md` before
status, cancellation, cleanup, review-packet, approval, or worktree operations.
Read `references/model-matrix.md` for detailed routing and live free-model
assessment rules.

## Bundled Files

- `scripts/delegate.py`: runner, state, model inventory, review packet, and review gate.
- `scripts/usage-report.sh`: worker-token, billing-class, and optional Codex-delta report.
- `scripts/dashboard-export.sh`: sanitized, versioned static dashboard snapshot.
- `scripts/spawn-opencode.sh`, `spawn-devin.sh`, `spawn-cursor.sh`: provider launchers.
- `scripts/model-policy.py`, `resolve-model.sh`: live free-model usability and routing.
- `references/runtime-contract.md`: state, review, process, and worktree contract.
- `references/model-matrix.md`: detailed task/model policy.
- `references/subagent-prompt-template.md`: bounded worker prompt.
- `references/task-manifest-template.json`: machine-readable scope.
