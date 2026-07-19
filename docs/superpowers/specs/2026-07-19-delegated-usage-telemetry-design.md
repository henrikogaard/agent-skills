# Delegated Usage Telemetry Design

## Purpose

Show how much model usage the delegated-subagents workflow moves away from
Codex, without presenting nominal API pricing as an actual subscription charge.

## Scope

Record provider-reported worker token usage for each attempt, preserve the raw
machine-readable source, and aggregate the normalized values by provider,
model, task, billing class, and date. Support an optional Codex session delta
so a report can compare external worker tokens with the supervising Codex
review window.

This first version does not scrape provider account dashboards, estimate
missing tokens from text length, or claim monetary savings when a provider is
free or subscription-funded.

## Usage Record

Every attempt may contain a normalized `usage` object:

```json
{
  "source": "provider-reported",
  "input_tokens": 1234,
  "cached_input_tokens": 800,
  "cache_write_tokens": 0,
  "output_tokens": 250,
  "reasoning_tokens": null,
  "total_tokens": 1484,
  "reported_cost_usd": 0.02,
  "billing_class": "free",
  "actual_charge_usd": 0
}
```

Missing values remain `null`; they are never converted to zero. `total_tokens`
counts input plus output when the provider does not supply a total. Cached input
remains a subset of input and is reported separately rather than added again.

`billing_class` is one of `free`, `subscription`, `included-codex`,
`api-paid`, or `unknown`. `reported_cost_usd` is provider or tool metadata;
`actual_charge_usd` is populated only when the charge is known. Free routes
record an actual charge of zero even if a tool reports API-equivalent pricing.

## Provider Capture

- **Devin:** parse per-step and final totals from the existing
  `devin-export.json` after the process exits.
- **OpenCode:** run with JSON output, retain that output as an attempt artifact,
  and parse token/cost fields. Record the session identifier when available so
  OpenCode's own export or stats can be used as evidence.
- **Cursor:** switch the wrapper from text to stream JSON and parse final usage
  fields when present. If the installed CLI omits them, record `source` as
  `unavailable`; do not estimate.
- **Codex:** an optional report argument accepts the current Codex rollout JSONL.
  The reporter compares the nearest cumulative `token_count` snapshots around
  the delegated run window. This is labeled `codex-session-delta` because it
  includes all supervising-task activity during that interval.

Provider parsing failures must not fail otherwise valid delegated work. They
produce an unavailable usage record and a compact diagnostic in state.

## Reporting

Add a `usage-report` command with JSON and compact table output. It reports:

- external input, cached input, output, reasoning, and total tokens;
- totals grouped by provider/model/task/billing class;
- actual known charge separately from reported nominal cost;
- capture coverage: measured attempts versus attempts with unavailable usage;
- optional Codex session delta and delegated token share.

The delegated share is `external_total / (external_total + codex_delta_total)`.
It is shown only when both values are available and their time windows overlap.

## Persistence And Privacy

Normalized usage is stored in the existing owner-only run state and model
history. Raw structured output remains inside the existing owner-only run
directory and is never copied into the Codex review packet. Reports expose
counts and identifiers, not prompts or transcripts.

## Verification

Tests cover Devin totals, OpenCode JSON events, Cursor usage-present and
usage-absent payloads, free/subscription billing semantics, aggregation,
coverage, optional Codex deltas, and malformed provider data. Existing runtime,
review-gate, isolation, and validator suites must stay green. The installed
skill is synced only after source validation passes.
