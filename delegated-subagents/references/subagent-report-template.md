# Subagent Report Template

```text
STATUS: success | partial | blocked | failed
MODEL: <provider/model>
TASK_TYPE: <scout|bulk|code-small|debug|review|closure-validation|long-autonomous>
REPO: <absolute path>
RUN_ID: <runtime run id>

SUMMARY:
<3-6 bullets with the actual result>

FILES_INSPECTED:
- <path>

FILES_CHANGED:
- <path> - <why>

SCOPE_CHECK:
- <all changes within manifest | exact out-of-scope path>

COMMANDS_RUN:
- <command> -> <result>

VERIFICATION:
- <check> -> <result>

REVIEW_FINDINGS:
- <severity, file:line, finding, or "none">

FINDING_DISPOSITION:
- <finding -> fixed|open|not-applicable>

ACCEPTANCE_CRITERIA:
- [pass|fail|unknown] <criterion> -> <evidence>

CLOSURE_RECOMMENDATION:
ready-for-pr | ready-for-review | needs-fix | blocked | not-implemented | not-applicable

RISKS_OR_BLOCKERS:
- <risk/blocker, exact decision needed from main Codex task, or "none">

FOLLOW_UPS:
- <follow-up or "none">
```
