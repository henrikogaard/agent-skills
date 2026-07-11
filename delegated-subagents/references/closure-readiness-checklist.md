# Closure Readiness Checklist

Require evidence for every applicable item:

- Issue acceptance criteria are explicit and each is marked pass, fail, or unknown.
- Changed files are within the task manifest and no unrelated diff is present.
- Focused tests, builds, typechecks, lint, UI/API checks, and migrations were run as applicable.
- Skipped verification has a concrete reason and residual risk.
- User-facing behavior, docs, worklog, and changelog follow repository rules.
- Branch has a clean ownership story and all completed work is committed or clearly handed off.
- A PR exists or the report explicitly recommends `ready-for-pr` with title/body evidence.
- CI and review findings are resolved or listed as blockers.
- Manual QA or user signoff is identified when repository policy requires it.
- Project status is `In review`, not `Done`, until the user explicitly approves closure.

The closure-validation subagent recommends a state. The main Codex task checks
the evidence and is the only actor that may prepare a PR, update project state,
or ask the user for signoff.
