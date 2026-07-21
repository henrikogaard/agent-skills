---
name: debugging-process
description: Use when diagnosing, reproducing, investigating, or fixing bugs, test failures, flaky behavior, regressions, production incidents, confusing errors, broken builds, failing CI, unexpected UI behavior, data issues, or "it doesn't work" reports.
---

# Debugging Process

Debug systematically: reproduce, isolate, form hypotheses, test them, fix the cause, and add regression coverage. The goal is to avoid patching symptoms or guessing from the first error message.

## When To Use

Use this skill when:

- A test, build, CI job, app workflow, migration, integration, or UI behavior is failing.
- The user reports a bug, regression, flaky behavior, crash, confusing error, or data inconsistency.
- The cause is not already obvious from a tiny local diff.
- A previous fix attempt did not work.

For a clear one-line typo or obvious compile error, fix directly and still verify.

## Workflow

1. Capture the symptom exactly: command, route, error, screenshot, log line, expected behavior, and actual behavior.
2. Reproduce or explain why reproduction is not possible in the current environment.
3. Minimize the failing case: narrow to file, input, route, test, commit range, config, or data condition.
4. Form 2-3 hypotheses and rank them by evidence.
5. Test one hypothesis at a time with targeted inspection, instrumentation, or focused commands.
6. Fix the root cause, not only the visible symptom.
7. Add or update regression coverage where practical.
8. Run targeted verification, then broaden only if the touched surface warrants it.

## Debugging Readout

Use this table for non-trivial investigations:

```markdown
Debugging status

| Step | Evidence | Result |
|---|---|---|
| Symptom | Exact error, command, route, or screenshot | Captured |
| Reproduction | Command or manual path | Reproducible / Not reproducible |
| Hypothesis | Suspected cause | Confirmed / Rejected / Pending |
| Fix | File and behavior changed | Implemented / Blocked |
| Regression check | Test or QA path | Passed / Not run |
```

End with:

```markdown
Root cause: [one sentence].
Verified: [commands and results, or not run with reason].
```

## Rules

- Do not make broad refactors during debugging unless they are necessary to fix the root cause.
- Do not claim a cause without evidence.
- Preserve logs and exact failing commands in the handoff.
- If a bug touches data, migrations, privacy, release behavior, or broad contracts, route through the relevant guard skill.
- Use `change-surface-map` when the failing behavior crosses modules.
- Use `verification-matrix` after the fix to choose targeted and broader checks.
- Use `review-before-commit` before publishing the fix.
- If `summary-tables` is available, use it for investigation and fix summaries.
