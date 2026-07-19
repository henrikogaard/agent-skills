# Delegated Usage Dashboard Implementation Plan

## Goal

Deliver a private, manually refreshed Sites dashboard for delegated-subagent
run and token usage, while making SWE-1.7 routing resilient to changing exact
model names and preserving the mandatory Codex final-review gate.

## Success Criteria

- The skill deterministically exports a versioned, sanitized dashboard snapshot
  without invoking a model.
- Stable model families and changing exact variants are both retained.
- Devin routing resolves a configured or observed SWE-1.7-family model instead
  of depending on one exact name.
- Every OpenCode route performs and records a live free-model inventory refresh.
- The dashboard passes unit, build, accessibility, responsive, and deployed-site
  checks.
- The installed skill matches the verified repository bundle.
- Changes are pushed in reviewable branches with no merge or public deployment.

## Task 1: Dynamic model identity and routing

**Files:**

- Modify `delegated-subagents/scripts/delegate.py`
- Modify `delegated-subagents/scripts/spawn-devin.sh`
- Modify `delegated-subagents/references/model-matrix.md`
- Modify `delegated-subagents/references/runtime-contract.md`
- Modify `delegated-subagents/SKILL.md`
- Add or modify focused tests under `delegated-subagents/tests/`

**Red:** Add tests for case/separator-tolerant SWE-1.7 family matching, Max and
Lightning variant extraction, unknown suffix preservation, billing
classification by family, explicit/configured/observed/compatibility precedence,
and provider rejection. Confirm the new tests fail for the expected missing
behavior.

**Green:** Add one normalized model-identity helper used by telemetry, dashboard
export, review-family checks, and Devin routing. Make the Devin wrapper accept a
family-level request and resolve the concrete model using the approved
precedence. Keep exact safe user requests first.

**Refactor/docs:** Remove duplicated substring checks and update the matrix to
name the SWE-1.7 family with dynamic variants rather than a permanent exact
model. Preserve live OpenCode refresh as a required selection step.

**Verify:** Run the focused resolver, usage, control CLI, and isolation tests.

## Task 2: Sanitized dashboard snapshot exporter

**Files:**

- Modify `delegated-subagents/scripts/delegate.py`
- Add `delegated-subagents/scripts/dashboard-export.sh`
- Modify `delegated-subagents/references/runtime-contract.md`
- Modify `delegated-subagents/SKILL.md`
- Add `delegated-subagents/tests/test_dashboard_export.py`

**Red:** Add fixtures and tests for deterministic aggregation, null-versus-zero
semantics, cache accounting, daily trends, family/variant groupings, optional
overlapping Codex deltas, empty history, malformed usage, and schema version
rejection. Add privacy tests that seed prompts, transcripts, repository paths,
session IDs, commands, and raw errors and prove none can enter the output.

**Green:** Add a `dashboard-export` command that consumes the existing usage
report internally, constructs only the approved allowlist fields, validates the
entire document, and writes atomically only after validation. Do not copy raw
run records and do not invoke a model.

**Verify:** Run the new exporter tests, `git diff --check`, the repository skill
validator, and the complete delegated-subagents test suite.

## Task 3: Sync and verify the installed skill

**Files:**

- Repository bundle under `delegated-subagents/`
- Installed bundle under `/Users/henrik/.codex/skills/delegated-subagents/`

After repository verification is green, sync only the changed skill files into
the installed bundle using the repository's established installation workflow.
Compare source and installed bundle contents, then run the installed preflight,
model refresh, exporter help, and focused tests. Do not copy dashboard snapshots
or local run state into the repository.

## Task 4: Create the standalone Sites source repository

Use the Sites connector to create exactly one source repository and persist the
returned project and repository identifiers in the connector-required hosting
configuration. If the connector remains unauthorized, stop at this task with
the exact connector error; do not substitute a public host.

The Sites repository will contain:

- a small typed web application;
- the versioned static snapshot schema and parser;
- a checked-in sanitized snapshot artifact;
- KPI, filter, chart, table, zero-state, and error-state components;
- unit/component tests and production build configuration;
- private deployment documentation.

No application route may read local files, provider APIs, Codex state, or
credentials at runtime.

## Task 5: Build the precision-dark executive dashboard test-first

**Red:** Add tests for schema parsing, KPI calculations, capture coverage,
delegated share eligibility, family rollups, variant drill-down, all filters,
cost-label semantics, unknown categories, empty state, and incompatible schema.

**Green:** Implement the approved header, static-snapshot status, KPI row,
provider/billing chart, model-family outcomes, daily trends, task/result
breakdown, recent measured attempts, and coverage diagnostics. Use shared
semantic colors, visible focus, keyboard-operable filters, reduced-motion
support, and responsive stacking.

**Verify:** Run unit/component tests, type checking, production build, automated
accessibility checks, and rendered desktop/mobile review. Confirm the built
assets contain none of the exporter privacy-fixture sentinels.

## Task 6: Publish one exact private Sites version

Regenerate and validate the real sanitized snapshot, copy only that artifact
into the Sites repository, commit explicit files, and push the exact tested
revision. Save a Sites version for that revision and deploy it owner-only.
Confirm deployment success and visually verify the production URL. A failure at
any stage leaves the prior private deployment intact.

Do not deploy publicly. Do not expose connector credentials or temporary source
credentials in files, logs, commands, or handoff text.

## Task 7: Final Codex review and review handoff

Review every changed line in both repositories, rerun focused verification, and
confirm snapshot totals against the command-line usage report. Check branch,
push, CI, Sites deployment, and installed-skill equivalence live.

Commit and push the scoped changes. Create or update ready-for-review PRs with
verification evidence, privacy notes, deployment state, and residual risks.
Do not merge either PR. Recommend acceptance only after the complete Codex
review passes.
