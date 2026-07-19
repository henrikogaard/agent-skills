# External Polish First Design

## Purpose

Reduce OpenAI subscription usage while preserving a mandatory, complete Codex
review before the supervising task recommends accepting delegated work.

The delegated worker should do the implementation, focused verification, and
self-review. A separate external reviewer should catch and repair routine
findings before Codex sees the final patch. Codex remains the sole final
reviewer and user-facing decision-maker.

## Goals

- Require a full Codex review of every final changed line before recommending
  acceptance.
- Keep implementation, routine investigation, repair loops, and evidence
  collection on external subscriptions or free routes when safe.
- Discover currently available free OpenCode models before every routing
  decision instead of relying on a stale static list.
- Prefer deterministic scripts over model calls for manifests, diff summaries,
  test evidence, state transitions, and review packets.
- Prevent a worker's self-reported success from being described as accepted.
- Preserve the existing explicit opt-in activation rule and managed-worktree
  safety boundary.

## Non-goals

- Delegating final acceptance, merge, release, deployment, security, privacy,
  migration, or product decisions.
- Automatically retrying weak patches across many providers.
- Treating a visible model as capable without task-fit or outcome evidence.
- Sending full worker transcripts, unbounded logs, or repository-wide context
  to Codex.

## Pipeline

1. **Codex scope contract**: Codex records the objective, acceptance criteria,
   allowed paths, risk tier, and focused verification requirements in a compact
   manifest.
2. **Live model discovery**: the runtime refreshes provider inventories and
   selects a task-fit route using the matrix below.
3. **External implementation**: one worker owns the bounded patch, focused
   tests, and self-review.
4. **Deterministic preflight**: scripts check scope, dirty paths, report shape,
   required commands, and manifest criteria without model reasoning.
5. **Independent external review**: a different provider or model family
   reviews the final diff. It reports findings but cannot approve the work.
6. **External repair**: the implementer repairs objective findings and reruns
   focused checks. Limit this to one repair cycle by default.
7. **Review packet**: a deterministic command produces a compact packet for
   Codex containing metadata, claims, evidence, risks, and the complete final
   diff.
8. **Mandatory Codex review**: Codex reviews every changed line, checks the
   acceptance evidence, and runs or requests proportionate final verification.
9. **Decision**: only Codex can record `approved`, `changes-required`, or
   `blocked`. Only `approved` permits a recommendation to accept.

Codex should not ingest intermediate worker logs or repeatedly poll healthy
workers. Status commands should return compact state snapshots.

## Enforced State Model

The runtime must stop using `accepted` for worker self-reports.

| State | Meaning |
|---|---|
| `running` | External work is active. |
| `worker-complete` | Worker report and scope policy passed; no review implied. |
| `pre-review-complete` | Independent external review finished and objective findings were resolved or recorded. |
| `codex-review-required` | Final review packet is ready. Acceptance is prohibited. |
| `changes-required` | Codex found issues; external repair may run once before a new review. |
| `blocked` | A user, credential, scope, product, or risk decision is required. |
| `approved` | Codex reviewed the complete final diff and acceptance evidence. |
| `rejected` | Report, scope, policy, or verification failed. |

An approval record must contain the reviewer identity `codex`, review time,
base commit, head/worktree identity, final diff hash, verification summary, and
residual risks. Any file change after approval changes the diff hash and
invalidates approval automatically.

If Codex previously reviewed a patch and a repair changes it, Codex may review
the repair delta plus the unchanged previously reviewed content. The hash chain
must prove that together these reviews cover the complete final diff.

## Live Free OpenCode Discovery

Before each OpenCode routing decision, run `opencode models` and parse its
current output. A free OpenCode model is one whose canonical identifier:

- starts with `opencode/`; and
- contains the case-insensitive token `free`, normally as the suffix `-free`.

Do not maintain the free inventory only as prose. Save the refreshed inventory
with its timestamp in runtime state and include it in routing evidence.

For every discovered free model:

1. Classify likely task fit using explicit matrix rules and conservative name
   patterns such as `code`, `flash`, or `ultra`.
2. Consult the local scorecard for the exact task type.
3. Mark it `usable`, `probe-only`, or `excluded` with a reason.
4. Treat an unknown free model as `probe-only`; it may scout or review a small
   fixture but may not become the default edit worker until a bounded smoke run
   succeeds.
5. Exclude a route after three comparable recent hard failures until it passes
   a new probe. Malformed-report failures must be distinguished from incorrect
   patches and provider failures.

If a usable free model fits, prefer it for scouting or external pre-review. Do
not force a weak free model onto implementation when SWE 1.7 or Composer is
more likely to avoid an expensive Codex repair cycle.

aiRouter is free for this installation but is discovered and classified as a
separate provider because its model names do not contain `free`.

## Model And Task Matrix

This matrix is policy, not a permanent availability list. Explicit user model
requests override it when allowed by safety rules.

| Task shape | Primary route | External polish/review | Fallback | Codex responsibility |
|---|---|---|---|---|
| Repository inventory, search, docs sweep | Best live usable `opencode/*free*`; prefer flash/general models | Optional second free model only when evidence conflicts | `airouter/Qwen3.6` | Review only the resulting decision-relevant evidence |
| Simple documentation or mechanical edit | Devin `swe-1.7` | Best live free code/review model | `composer-2.5-fast` | Full final diff review |
| Bounded bug fix or small feature | Devin `swe-1.7` after integration smoke passes | `composer-2.5-fast` or a usable independent free reviewer | `composer-2.5` | Full final diff and acceptance review |
| Debugging with unclear cause but bounded surface | `composer-2.5` | Devin `swe-1.7` or Mistral Medium | Mistral Medium | Confirm root cause and review complete final diff |
| Complex multi-file implementation with approved design | `composer-2.5` | Devin `swe-1.7` or Mistral Medium from another model family | Main Codex implementation if external attempts fail | Own integration decisions and full final review |
| Independent pre-review | A provider/model family different from implementer; prefer usable free model, SWE 1.7, or Composer Fast | Not applicable | Mistral Medium | Resolve findings and make final decision |
| Closure evidence collection | Best live usable free review/general model | Deterministic checklist | `airouter/Qwen3.6` | Validate evidence; only Codex recommends closure |
| Large decomposable epic | Composer 2.5 coordinates bounded SWE/free workers | Independent provider reviews each slice | Mistral Medium coordination only when requested | Approve decomposition and review each integration-ready final slice |
| Security, privacy, auth, migration, billing, release | Strongest task-fit external model may investigate or implement bounded work | Independent strong external review | None automatically | Own design, risk decisions, full review, and all external actions |

Subscription/cost labels must be recorded explicitly:

- Devin `swe-1.7`: free for this installation.
- `airouter/*`: free for this installation.
- `opencode/*free*`: free as reported by the live model inventory.
- Cursor Composer: subscription-limited with a generous allowance.
- Mistral: subscription-limited.
- Main/native Codex: scarce OpenAI subscription; reserve for scoping, final
  review, integration, and decisions.

## Cursor Integration

Add `cursor` as a first-class runtime tool with a `spawn-cursor.sh` wrapper.
Use the authenticated `cursor-agent` CLI in non-interactive print mode, closed
stdin, an explicit model, an explicit workspace, and managed isolation.

- `composer-2.5-fast`: scouting, mechanical edits, review-packet preparation,
  and low-risk external pre-review.
- `composer-2.5`: bounded implementation, debugging, repair, and coordination
  across approved independent slices.

Cursor may coordinate low-risk workers, collect evidence, and recommend
`codex-review-required`. It cannot create the final approval record.

## Review Packet

The generated packet must include:

- Run, repository, branch/worktree, base commit, and selected models.
- Risk tier and allowed paths.
- Complete final changed-path list and diff stat.
- Worker summary limited to six bullets.
- External reviewer findings and disposition.
- Acceptance criteria with concise file/line or command evidence.
- Focused verification results and exact skipped checks.
- Residual risks and decisions needed.
- Complete final unified diff, with generated or binary files identified
  separately.
- SHA-256 hash of the canonical final diff.

The packet must exclude complete transcripts, repeated prompts, environment
dumps, dependency trees, and full passing test logs. Codex may request a narrow
source excerpt or failure log when the packet exposes a specific gap.

## Failure And Retry Policy

- Default to one implementer attempt, one independent pre-review, and one
  repair cycle.
- Do not retry malformed scope, incorrect code, failed tests, or policy
  violations by silently switching providers.
- Provider unavailability may select the next announced route.
- If external polish cannot produce a reviewable patch, return control to Codex
  with compact evidence instead of accumulating more external attempts and
  parent context.
- A failed free-model probe must not block SWE, Composer, or an explicitly
  requested subscription route.

## Validation

Implementation must add tests for:

- Live discovery and filtering of `opencode/*free*` identifiers.
- Task-fit classification, scorecard use, and unknown-model probe behavior.
- Cursor command construction and permission/isolation mapping.
- Worker completion never creating `approved` or legacy `accepted` state.
- Approval rejection before a Codex review record exists.
- Diff-hash invalidation after any file change.
- Review-packet inclusion and transcript/log exclusion.
- One-review and one-repair default limits.
- Compatibility or migration behavior for existing terminal run states.

Run the repository validator and the complete delegated-subagents test suite.
Sync the installed skill only after the source bundle passes validation.

## Documentation Updates

- Shorten `SKILL.md` to the routing and mandatory-review contract.
- Keep operational details in focused references loaded only when needed.
- Replace the static free-model section with the discovery and usability rules.
- Update the runtime contract and examples to use the new states.
- Keep `agents/openai.yaml` explicit opt-in metadata aligned with `SKILL.md`.
