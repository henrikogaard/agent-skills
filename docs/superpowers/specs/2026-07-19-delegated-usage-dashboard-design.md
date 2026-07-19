# Delegated Usage Dashboard Design

## Status

Approved design for a private, manually refreshed Sites dashboard and the
supporting delegated-subagents model normalization. Implementation has not
started.

## Purpose

Make delegated-subagent usage visible without spending additional model tokens
to produce the report. The dashboard must show how many delegated runs have
occurred, which external providers and model families performed the work, how
much provider-reported token usage was captured, and how much of the comparable
worker-plus-Codex usage was delegated.

The dashboard is an observability aid. It does not weaken the existing rule
that Codex performs the complete final review before recommending acceptance.

## Approved Decisions

- Use the **External polish first** workflow already defined by this skill.
- Publish a private, owner-only OpenAI Sites dashboard.
- Use a static, sanitized snapshot generated locally and refreshed manually.
- Use the **executive overview** information architecture and **precision dark**
  visual style.
- Normalize changing model names into stable families while retaining every raw
  model name and variant.
- Apply dynamic model-family handling to both dashboard grouping and worker
  routing.
- Refresh the live OpenCode inventory before every OpenCode routing decision and
  evaluate all currently visible free models for task fit.

## Scope

This work has two bounded deliverables:

1. Extend the `delegated-subagents` skill with a sanitized dashboard exporter
   and dynamic model-family resolution.
2. Create a standalone Sites source repository that renders the exported
   snapshot without access to local Codex or worker state.

The skill repository remains the source of truth for usage semantics, model
normalization, routing policy, snapshot schema, and exporter tests. The Sites
repository owns only the presentation application and its UI tests.

## Non-goals

- Live telemetry, background refresh, or direct production access to
  `~/.codex`, worker transcripts, provider accounts, or provider billing APIs.
- Scraping Cursor, Devin, Mistral, or OpenAI subscription dashboards.
- Estimating missing tokens from output length.
- Treating API-equivalent nominal cost as an actual subscription charge.
- Replacing Codex final review with a dashboard status or worker assertion.
- Predicting future provider names beyond conservative family matching and
  explicit configuration.

## Architecture

```text
owner-only delegated run state
            |
            v
usage-report --json + model normalizer
            |
            v
dashboard-export (aggregate, sanitize, validate)
            |
            v
versioned static snapshot JSON
            |
            v
Sites source repository -> saved Sites version -> private deployment
```

The exporter runs locally. It invokes the existing deterministic usage report,
normalizes model identities, strips sensitive fields, validates the complete
snapshot, and writes a single versioned JSON artifact. The Sites application
loads that artifact at build time or as a bundled static asset and performs all
filtering in the browser. It has no server endpoint and no credential or local
filesystem access.

The manual refresh sequence is:

1. Regenerate the sanitized snapshot locally.
2. Validate its schema, privacy rules, totals, and internal consistency.
3. Commit and push the exact snapshot and dashboard source state.
4. Save a Sites version from that exact source revision.
5. Deploy the version privately with owner-only access.
6. Confirm deployment status and render the deployed dashboard.

If generation or validation fails, no source revision or Sites version is
published. The last valid private deployment remains available.

## Snapshot Contract

The top-level document contains:

```json
{
  "schema_version": 1,
  "generated_at": "2026-07-19T14:30:00Z",
  "window": {"from": null, "to": "2026-07-19T14:30:00Z"},
  "summary": {},
  "groups": [],
  "trends": [],
  "attempts": [],
  "coverage": {}
}
```

`summary` contains run count, attempt count, measured and unavailable attempt
counts, capture coverage, external input/output/reasoning/total tokens,
cache-read tokens, known actual charge, unknown-charge attempt count, and the
optional Codex session delta. Delegated share is emitted only when external
tokens and a comparable overlapping Codex delta are both present.

`groups` contains aggregate rows by provider, model family, raw model, variant,
task type, result, and billing class. `trends` contains daily aggregates.
`attempts` contains only dashboard-safe recent attempt facts: timestamp,
provider, normalized model fields, task type, result, usage availability,
token counts, and billing classification.

Null means unknown or unavailable. It must never be rewritten to zero. Cached
input is shown as a subset of input and is not double-counted in total tokens.

## Model Identity And Dynamic Routing

Every captured or selected model uses these fields:

| Field | Meaning |
|---|---|
| `raw_model` | Exact provider-reported or configured identifier. |
| `model_family` | Stable policy identity such as `swe-1.7` or `composer-2.5`. |
| `display_name` | Human-readable raw name, preserving provider capitalization. |
| `variant` | Optional changing suffix such as `max`, `lightning`, or a future value. |
| `billing_class` | `free`, `subscription`, `included-codex`, `api-paid`, or `unknown`. |

The Devin family matcher recognizes conservative separator and case variations
of the `SWE-1.7` stem. For example, `SWE-1.7 Max Beta` and `SWE-1.7 Lightning
Beta` both group under `swe-1.7`, while `max` and `lightning` remain visible as
separate variants. A previously unseen suffix is preserved as an unknown
variant; it is not silently promoted to a known capability or billing class.

Routing policy refers to the stable family, not a permanent exact string. The
runtime resolves a concrete Devin model in this order:

1. an explicit safe model requested by the user;
2. an exact configured model for the family;
3. a recently successful observed model for the family;
4. the documented compatibility alias, only when no more specific identifier
   is available.

The resolution evidence records both family and concrete name. Provider
rejection is reported compactly and follows the announced fallback chain; the
runtime does not invent a likely future model name.

Before every OpenCode selection, `refresh-models.sh` must call the live model
list and reassess every identifier whose canonical name indicates it is free.
The route considers current visibility, task-fit patterns, scorecard outcomes,
and recent hard failures. New free models start as `probe-only` until a bounded
smoke run establishes them for the requested task. A failed refresh cannot be
presented as a current free-model check; routing either uses an explicitly
allowed non-OpenCode fallback or stops with the refresh failure.

## Dashboard Information Architecture

The default desktop view is a dense executive overview with responsive stacking
for smaller screens.

### Header and filters

The header shows the dashboard title, snapshot timestamp, covered date range,
and a clear `Static snapshot` status. Filters cover date, provider, model
family, variant, task type, result, and billing class. A reset action restores
the complete snapshot.

### Key metrics

The first row shows delegated runs, attempts, measured attempts, capture
coverage, delegated total tokens, and cache-read tokens. When a comparable
Codex delta exists, a separate card shows delegated share and labels the exact
comparison window.

### Analysis panels

- Token consumption by provider and billing class.
- Model-family outcomes with expandable raw names and variants.
- Daily run, token, and measurement-coverage trends.
- Task-type and result breakdown.
- Recent measured attempts, including the exact model variant.
- Coverage and unavailable-usage diagnostics.

Historical `SWE-1.7`, current `SWE-1.7 Max`, `SWE-1.7 Lightning`, and future
matched variants remain independently filterable while rolling up to the same
family.

### Cost presentation

Known actual charge and provider-reported nominal cost are separate metrics.
Free routes may show a known actual charge of `$0`. Subscription-funded routes
with no charge evidence show `Unknown`, never `$0`. Nominal API-equivalent cost
is labeled as informational and is never described as savings.

## Visual Direction

The precision-dark style uses a near-black neutral canvas, restrained graphite
panels, crisp borders, compact typography, and a small number of semantic
accents. Data density takes priority over decorative effects. Charts use the
same color for a category across the dashboard, provide text or table
equivalents, and do not rely on color alone.

The interface must support keyboard navigation, visible focus states, readable
contrast, reduced-motion preferences, and useful layouts from narrow mobile to
wide desktop widths.

## Privacy And Security

The exporter uses an allowlist schema. It must not publish prompts, transcripts,
review packets, repository or worktree paths, branch names, session identifiers,
raw provider errors, command lines, environment values, credentials, or file
contents. Diagnostics are normalized to enumerated reason codes and aggregate
counts.

The snapshot is suitable only for the private dashboard even after sanitation;
it must not be deployed publicly by default. Sites deployment is owner-only.
Connector credentials and temporary source credentials are never written into
the repository, snapshot, shell history, logs, or final handoff.

## Error Handling

- Empty valid history renders zero-state guidance and the snapshot timestamp.
- Missing or malformed snapshot data fails the production build or exporter
  validation instead of rendering misleading totals.
- Unknown providers, models, variants, and billing classes remain visible as
  `unknown` categories with their safe raw model label when allowed.
- Attempt-level parser failures increase the unavailable count without failing
  an otherwise valid delegated run.
- A failed Sites save or deploy leaves the previous deployment intact and is
  reported with the exact failed stage.
- Schema changes require a new `schema_version`; the dashboard rejects versions
  it does not understand.

## Verification

### Skill repository

Tests must cover snapshot aggregation, allowlist sanitation, forbidden-value
rejection, null-versus-zero semantics, totals and cache accounting, coverage,
optional overlapping Codex deltas, dynamic Devin family and variant matching,
unknown variants, concrete-model precedence, live OpenCode free-model refresh,
and refresh failure behavior.

The repository skill validator and complete delegated-subagents test suite must
remain green. The installed skill is synced only after source verification.

### Sites repository

Tests must cover schema parsing, KPI calculations, filters, family rollups,
variant drill-down, unknown and empty states, cost labels, and malformed
snapshots. Verification also includes type checking, production build, keyboard
navigation, responsive rendering, and a visual check of the deployed private
site.

## Acceptance Criteria

- A manual command produces a deterministic, validated, sanitized snapshot from
  the local delegated usage state without invoking a model.
- The private dashboard accurately shows runs, attempts, coverage, worker token
  usage, cache reads, model/provider/task/result breakdowns, and optional Codex
  comparison data.
- A viewer can distinguish stable model families from changing exact names and
  variants.
- Routing can use `SWE-1.7 Max`, `SWE-1.7 Lightning`, or a later configured or
  observed family variant without changing the policy matrix.
- Every OpenCode routing decision performs and records a live free-model check.
- No prohibited local or worker data appears in the snapshot or built site.
- The exact tested source revision is saved and deployed through Sites with
  owner-only access.
- The mandatory complete Codex final-review gate remains unchanged.
