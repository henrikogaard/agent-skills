---
name: summary-tables
description: Use when the user needs a summary, status update, comparison, acceptance-criteria check, implementation close-out, gap analysis, verification matrix, PR/issue readiness report, review suggestions, fix summary, open-issue report, or decision-ready readout; triggers include "summary table", "plan summary", "acceptance criteria", "gap vs plan", "what shipped", "status", "verification", "checklist", "issue", "PR summary", "progress update", "readout", or "comparison".
---

# Summary Tables

Use concise Markdown tables to make planning, reporting, and presentation of decision-relevant information scannable. Prefer this format when summarizing work against a plan, issue, PR, acceptance criteria, findings list, commit/push result, verification checklist, or any other status-oriented readout.

## Readout Shape

For status and close-out summaries, use the Claude-style readout shape:

1. Start with the bottom line in one sentence: what is done, what remains, branch/commit/PR state, and whether verification is still pending.
2. Add a short section label that says what the table answers, such as `What changed`, `Suggestions`, `Are all started issues implemented?`, or `Still open`.
3. Use one compact table with columns tailored to the question. Avoid one-size-fits-all columns.
4. Close with a short verification/net line or a tiny supporting section for details that do not fit cleanly in the table.

Good table columns are concrete nouns from the task:

| Use case | Prefer columns |
|---|---|
| Review fixes | `#`, `Suggestion`, `Fix` |
| Fresh review suggestions | `#`, `File`, `Suggestion`, `Category` |
| Issue implementation status | `Issue`, `Implementation`, `On` |
| Open issue report | `Issue`, `Status` |
| Plan progress | `#`, `Plan item`, `Status` |
| Acceptance criteria | `Acceptance criterion`, `Status` |
| Verification | `Target`, `Result`, `Evidence` |
| Risk/comparison | `Option`, `Tradeoff`, `Recommendation` |

When the user asks a direct yes/no status question, answer directly before the table:

```markdown
Yes — every started item is implemented. One issue comment was stale and is now corrected.

Are all started issues implemented?

| Issue | Implementation | On |
|---|---|---|
| `#340` | Complete — cookie-only session handling and grace value landed | `development` |
| `#342` | Complete — all three review parts fixed | `development` |

Net: no issue is half-done; remaining work is closeout/merge bookkeeping.
```

## Table Patterns

For review suggestions and fixes, prefer an itemized table:

```markdown
What changed

| # | Suggestion | Fix |
|---|---|---|
| 1 | Refresh trace lingers in `localStorage` | Added `clearRefreshTrace()` on explicit sign-out; preserved auth-failure traces for diagnostics. Tested. |
| 2 | Duplicated retry helper | Reused core retry timing helper instead of a local copy. |

Verified: focused tests passed; CI still pending.
```

For fresh suggestions, keep the finding, location, and category separate:

```markdown
Suggestions

| # | File | Suggestion | Category |
|---|---|---|---|
| 1 | `refreshTrace.ts` | Clear the debug trace on sign-out to avoid stale shared-machine breadcrumbs. | Maintainability/Privacy |
| 2 | `authRetry.ts` | The helper overlaps with core retry code; consider reusing the shared helper. | Maintainability |
```

For issue status, group tables by real state instead of mixing everything:

```markdown
Implemented on `development`

| Issue | Status |
|---|---|
| `#342` Retry-after and circuit breaker | Fully done — all review parts fixed |
| `#343` Observability surfacing | Partial — Part 1 done; Parts 2-3 remain |

Not started
- `#331` Local-first sync
- `#329` Automation engine

Blocked / operational
- `#284` OAuth provider setup — waiting on production credentials
```

For gap/progress against a plan, use:

```markdown
Gap vs the #123 plan:

| # | Plan item | Status |
|---|---|---|
| 1 | Short plan item | ❌ Not started |
| 2 | Short plan item | ⚠️ Partial — concrete evidence and what is missing |
| 3 | Short plan item | ✅ Done — implementation/test/docs evidence |
```

For acceptance criteria, use:

```markdown
Cross-checking each acceptance criterion against the current work:

| #123 Acceptance criterion | Status |
|---|---|
| User-visible criterion | ✅ Concrete code path + test/doc evidence |
| User-visible criterion | ⚠️ Partial — shipped part; missing part |
| User-visible criterion | ❌ Missing — what does not exist yet |
```

For verification, use a short list after the table:

```markdown
Verification targets:
- ✅ Focused tests passed
- ⚠️ Manual QA not run — needs interactive session
- ❌ Integration test failing — failure reason
```

End with one compact recommendation paragraph:

```markdown
This is a meaningful chunk of work because [...]. Next step: [...].
```

## Grouping Rules

Group long status readouts by actual state before creating a table:

- `Done / implemented`: shipped or fixed, ideally with branch/commit/issue evidence.
- `Partial`: some parts landed; name the remaining pieces.
- `Open / not started`: no implementation yet; name priority or reason if known.
- `Blocked`: external credential, environment, review, CI, or dependency is missing.
- `Operational / bookkeeping`: merge, close, comment, label, board, deploy, or CI follow-up.

Use separate headings or short lead-in lines for groups. Do not bury `Partial` or `Blocked` rows inside a long table of completed work.

## Preserve Valuable Detail

Tables organize the summary; they must not erase useful information. Before finalizing, scan the conversation and tool results for unique, decision-relevant facts and keep them either in the table evidence cells or in short supporting sections below the table.

Preserve these details when present:

- Changed files, components, migrations, docs, generated artifacts, and UI routes.
- User-visible behavior that now works.
- Verification commands, test counts, browser/manual QA targets, and skipped checks with reasons.
- Commit SHA, branch, push target, PR/issue numbers, issue state, labels, assignee, project/status, and posted comments.
- Findings with severity, file names, line numbers, exploit/impact notes, and must-fix recommendations.
- Follow-up plans, saved plan filenames, worklog breadcrumbs, and execution options.
- Excluded or unrelated local leftovers so the user knows what was intentionally not committed or handled.

When a status cell would become crowded, keep the row compact and add one of these blocks after the table:

```markdown
Main pieces:
- `path/File.ext` - what changed

What's working:
- User-visible behavior or route that was verified

Validation:
- `command` passed
- focused tests: `45 passed`

Commit / issue:
- commit `abc1234` on `feature/name`
- pushed to `origin/feature/name`
- issue `#123` moved to `In review`

Left out:
- unrelated local file or artifact not included

Execution options:
1. Option name: concise tradeoff
2. Option name: concise tradeoff
```

## Status Semantics

Use status symbols consistently when they improve scanning, especially in section lead-ins or verification bullets. In table cells, plain labels like `Complete`, `Partial`, `Blocked`, and `Pending` are often easier to read when the table is dense.

- ✅ Complete, verified, or evidence-backed.
- ⚠️ Partial, risky, uncertain, or needs follow-up.
- ❌ Missing, not started, failed, or contradicted by evidence.
- ⏳ Pending or intentionally deferred.
- 🚫 Blocked by an external dependency or unavailable environment.

Each status cell must include evidence, not just a label. Name files, commands, tests, commits, docs, UI surfaces, or known missing pieces when available. Use `code` formatting for identifiers, commands, branch names, fields, functions, and exact status values.

## Writing Rules

Keep the table compact and factual. Do not pad rows with generic prose.

Lead with the answer. If the user asks "are all issues done?", do not start with methodology; state `Yes`, `No`, or `Partially`, then give the table evidence.

Prefer 2-4 columns. If a fifth column feels necessary, consider moving low-value detail into a short paragraph or bullet list below the table.

Use concise section labels rather than long explanatory headings: `What changed`, `Suggestions`, `Still open`, `Verification`, `Net`.

Do not over-compress. If the original material contains important bullets, preserve each unique actionable fact unless it is duplicate, irrelevant, or pure noise.

Preserve the user's issue/PR/plan numbering when known, such as `#220` or `#221`.

If evidence is unknown or verification was not run, say so directly and include the reason. Do not imply completion from intent.

When producing a plan before implementation, use the same table shape with statuses like `Planned`, `Open`, `Needs decision`, or `Blocked`, then summarize scope and sequencing below it.

For more than about 8-12 rows, group related work into sections or summarize low-risk repeated items so the output remains readable.

End with a `Verified:` or `Net:` line when it helps:

```markdown
Verified: core 442, api 366, web 393; typecheck + lint clean.

Net: NOW + NEXT reliability work is done; remaining buildable work is `#343` Parts 2-3 and the later feature epics.
```

Use normal prose when the user asks a simple question that does not involve plans, acceptance criteria, status, verification, or work summaries.
